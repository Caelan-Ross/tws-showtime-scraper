"""Scrapes anime movies from the Landmark Cinemas API.

Paginates through GetComingSoon, filters for Japanese-language titles,
cross-validates against AniList, and downloads posters locally.
"""

import os
import re
import json
import time
import math
import requests
from datetime import datetime, date
from constants import (
    LANDMARK_API_URL,
    LANDMARK_API_HEADERS,
    LANDMARK_OUTPUT,
    ANILIST_URL,
    STATIC_POSTERS_DIR,
)

_anilistCache = {}


_EVENT_SUFFIXES = re.compile(
    r"\s+-\s+.+$"                                                          # "Title - Subtitle"
    r"|\s+\d+(st|nd|rd|th)\s+Anniversary.*$"                              # "Title 25th Anniversary..."
    r"|\s+(Anniversary|Celebration|Special|Event|Screening|Festival|Fest)" # keyword-triggered
    r".*$",
    re.IGNORECASE,
)


def _stripQualifiers(title):
    """Remove trailing parentheticals like '(Japanese w EST)' for cleaner lookups."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()


def _candidateTitles(title):
    """Yield progressively shorter search candidates for AniList."""
    base = _stripQualifiers(title)
    yield base
    # Also try stripping common theatrical event suffixes
    shorter = _EVENT_SUFFIXES.sub("", base).strip()
    if shorter and shorter != base:
        yield shorter


def _queryAnilist(searchTitle):
    """Single AniList query; returns True if a match is found, False otherwise."""
    query = """
    query ($search: String) {
      Media(search: $search, type: ANIME) { id }
    }
    """
    try:
        resp = requests.post(
            ANILIST_URL,
            json={"query": query, "variables": {"search": searchTitle}},
            timeout=10,
        )
        return resp.json().get("data", {}).get("Media") is not None
    except Exception:
        return False
    finally:
        time.sleep(0.7)


def _inAnilist(title):
    """Return True if AniList recognises the title as anime using progressive fallback."""
    if title in _anilistCache:
        return _anilistCache[title]

    found = False
    for candidate in _candidateTitles(title):
        if _queryAnilist(candidate):
            found = True
            break

    _anilistCache[title] = found
    return found


def _isAnime(title):
    """Japanese-language or Ghibli titles cross-validated with AniList."""
    titleLower = title.lower()
    if "japanese" not in titleLower and "ghibli" not in titleLower:
        return False
    return _inAnilist(title)


def _normalizeTitle(title):
    cleaned = re.sub(r"\s*\([^)]*\)\s*", " ", title).strip()
    return re.sub(r"[^a-z0-9]", "", cleaned.lower())


def _parseReleaseDate(dateStr):
    """Parse MM-DD-YYYY or MM/DD/YYYY into a date object."""
    if not dateStr:
        return None
    try:
        return datetime.strptime(dateStr.replace("-", "/"), "%m/%d/%Y").date()
    except (ValueError, AttributeError):
        return None


def _formatDate(releaseDate):
    if not releaseDate:
        return None
    return releaseDate.strftime("%B %-d, %Y")


def _statusLabel(releaseDate):
    if not releaseDate:
        return "Coming Soon"
    return "Now Playing" if releaseDate <= date.today() else "Coming Soon"


def _slugify(text):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return "lmk-" + (slug[:55] or "poster")


def _downloadPoster(title, url):
    if not url:
        return None

    slug = _slugify(title)

    for existing in os.listdir(STATIC_POSTERS_DIR):
        if existing.startswith(f"{slug}."):
            return f"posters/{existing}"

    try:
        r = requests.get(url, headers=LANDMARK_API_HEADERS, timeout=15)
        r.raise_for_status()

        contentType = r.headers.get("Content-Type", "image/jpeg")
        ext = contentType.split("/")[-1].split(";")[0].strip()
        if ext == "jpeg":
            ext = "jpg"
        filename = f"{slug}.{ext}"
        filepath = os.path.join(STATIC_POSTERS_DIR, filename)

        with open(filepath, "wb") as fileHandle:
            fileHandle.write(r.content)

        return f"posters/{filename}"
    except (requests.RequestException, OSError) as e:
        print(f"[landmark] Poster download failed for {title}: {e}")
        return None


def _fetchAllMovies():
    """Paginate through the GetComingSoon API and return all items."""
    allItems = []
    page = 1

    while True:
        resp = requests.get(
            LANDMARK_API_URL,
            params={"currentPage": page},
            headers=LANDMARK_API_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("Items", [])
        if not items:
            break
        allItems.extend(items)

        totalItems = data.get("TotalItems", 0)
        if page >= math.ceil(totalItems / len(items)):
            break
        page += 1

    return allItems


def _removeOrphanPosters(keptFiles):
    if not os.path.isdir(STATIC_POSTERS_DIR):
        return
    removed = 0
    for filename in os.listdir(STATIC_POSTERS_DIR):
        if not filename.startswith("lmk-"):
            continue
        if filename in keptFiles:
            continue
        filepath = os.path.join(STATIC_POSTERS_DIR, filename)
        try:
            if os.path.isfile(filepath):
                os.remove(filepath)
                removed += 1
        except OSError as e:
            print(f"[landmark] Failed to remove {filepath}: {e}")
    if removed:
        print(f"[landmark] Removed {removed} orphaned poster(s)")


def _writeOutput(movies, error=None):
    payload = {
        "scraped_at": datetime.now().isoformat(),
        "source": "landmark-api",
        "movies": movies,
    }
    if error:
        payload["error"] = error
    with open(LANDMARK_OUTPUT, "w") as fileHandle:
        json.dump(payload, fileHandle, indent=2)


def scrapeAnimeMovies(excludeTitles=None):
    """Scrape Landmark Cinemas anime from the GetComingSoon API.

    excludeTitles: set of normalized titles already covered by another source.
    Returns list of movie dicts.
    """
    normalizedExcludes = excludeTitles or set()

    try:
        allMovies = _fetchAllMovies()
    except requests.RequestException as e:
        print(f"[landmark] API fetch failed: {e}")
        _writeOutput([], error=str(e))
        return []

    os.makedirs(STATIC_POSTERS_DIR, exist_ok=True)
    keptFiles = set()
    results = []

    for movie in allMovies:
        title = movie.get("Title", "")
        if not _isAnime(title):
            continue
        if _normalizeTitle(title) in normalizedExcludes:
            print(f"[landmark] Skipping '{title}' — already in Cineplex listing")
            continue

        releaseDate = _parseReleaseDate(movie.get("ReleaseDate"))
        status = _statusLabel(releaseDate)
        posterUrl = movie.get("FilmImgSrc") or None
        friendlyName = movie.get("FriendlyName", "")
        detailUrl = f"https://www.landmarkcinemas.com/film-info/{friendlyName}"

        localPath = _downloadPoster(title, posterUrl)
        if localPath:
            keptFiles.add(os.path.basename(localPath))

        results.append({
            "title": title,
            "status": status,
            "release_date": _formatDate(releaseDate),
            "release_date_iso": releaseDate.isoformat() if releaseDate else "9999-12-31",
            "poster_url": posterUrl,
            "detail_url": detailUrl,
            "local_poster": localPath,
            "showtimes": [],
        })

    results.sort(key=lambda m: (m["status"] != "Now Playing", m["release_date_iso"]))

    _removeOrphanPosters(keptFiles)
    _writeOutput(results)
    print(f"[landmark] Done — {len(results)} anime movies (from {len(allMovies)} total)")
    return results


if __name__ == "__main__":
    scrapeAnimeMovies()
