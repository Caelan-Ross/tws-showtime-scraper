"""Fetches anime/Japanese-language movies from the Cineplex theatrical API.

Replaces the old HTML scraper with a direct API call.
Posters are downloaded to STATIC_POSTERS_DIR for local serving.
"""

import os
import re
import requests
import json
from datetime import datetime
from constants import (
    CINEPLEX_API_URL,
    CINEPLEX_API_HEADERS,
    CINEPLEX_IMAGE_HEADERS,
    CINEPLEX_OUTPUT,
    CINEPLEX_TAKE,
    STATIC_POSTERS_DIR,
    ANILIST_URL,
)

_anilistCache = {}


def _stripQualifiers(title):
    """Remove trailing parentheticals like '(Japanese w/e.s.t)' for cleaner lookups."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()


def _inAnilist(title):
    """Return True if AniList recognises the title as anime. Results are cached."""
    cleaned = _stripQualifiers(title)
    if cleaned in _anilistCache:
        return _anilistCache[cleaned]

    query = """
    query ($search: String) {
      Media(search: $search, type: ANIME) { id }
    }
    """
    try:
        resp = requests.post(
            ANILIST_URL,
            json={"query": query, "variables": {"search": cleaned}},
            timeout=10,
        )
        found = resp.json().get("data", {}).get("Media") is not None
    except Exception:
        found = False

    _anilistCache[cleaned] = found
    return found


def _isAnime(movie):
    """Match anime by genre tag, title keyword, or AniList lookup."""
    genres = movie.get("genres") or []
    name = movie.get("name") or ""
    if "Anime" in genres or "anime" in name.lower():
        return True
    if "japanese" in name.lower():
        return _inAnilist(name)
    return False


def scrapeAnimeMovies():
    try:
        resp = requests.get(
            CINEPLEX_API_URL,
            params={
                "language": "en-us",
                "skip": 0,
                "take": CINEPLEX_TAKE,
                "filterEvents": "false",
                "removeIrrelevantFilms": "true",
            },
            headers=CINEPLEX_API_HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[cineplex] API fetch failed: {e}")
        _writeOutput([], error=str(e))
        return []

    allMovies = data.get("items", [])
    anime = [m for m in allMovies if _isAnime(m)]
    anime.sort(key=lambda m: m.get("releaseDate") or "9999")

    os.makedirs(STATIC_POSTERS_DIR, exist_ok=True)
    keptFiles = set()
    results = []

    for movie in anime:
        posterUrl = movie.get("mediumPosterImageUrl")
        title = movie["name"]
        localPath = _downloadPoster(title, posterUrl)

        entry = {
            "title": title,
            "status": _statusLabel(movie),
            "release_date": _formatDate(movie.get("releaseDate")),
            "poster_url": posterUrl,
            "detail_url": movie.get("detailPageUrl"),
            "local_poster": localPath,
            "genres": movie.get("genres", []),
            "language": movie.get("language"),
            "runtime": movie.get("runtimeInMinutes"),
        }

        if localPath:
            keptFiles.add(os.path.basename(localPath))
        results.append(entry)

    _removeOrphanPosters(keptFiles)
    _writeOutput(results)
    print(f"[cineplex] Done — {len(results)} anime movies (from {len(allMovies)} total)")
    return results


def _statusLabel(movie):
    if movie.get("isNowPlaying"):
        return "Now Playing"
    if movie.get("isComingSoon"):
        return "Coming Soon"
    return None


def _formatDate(dateStr):
    if not dateStr:
        return None
    try:
        dt = datetime.fromisoformat(dateStr.replace("Z", "+00:00"))
        return dt.strftime("%B %-d, %Y")
    except (ValueError, AttributeError):
        return dateStr


def _slugify(text):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug[:60] or "poster"


def _downloadPoster(title, url):
    if not url:
        return None

    slug = _slugify(title)

    for existing in os.listdir(STATIC_POSTERS_DIR):
        if existing.startswith(f"{slug}."):
            return f"posters/{existing}"

    filepath = os.path.join(STATIC_POSTERS_DIR, f"{slug}.jpg")

    try:
        r = requests.get(url, headers=CINEPLEX_IMAGE_HEADERS, timeout=15)
        r.raise_for_status()

        contentType = r.headers.get("Content-Type", "image/jpeg")
        ext = contentType.split("/")[-1].split(";")[0].strip()
        if ext == "jpeg":
            ext = "jpg"
        filename = f"{slug}.{ext}"
        filepath = os.path.join(STATIC_POSTERS_DIR, filename)

        with open(filepath, "wb") as f:
            f.write(r.content)

        return f"posters/{filename}"
    except (requests.RequestException, OSError) as e:
        print(f"[cineplex] Poster download failed for {title}: {e}")
        return None


def _writeOutput(movies, error=None):
    payload = {
        "scraped_at": datetime.now().isoformat(),
        "source": "cineplex-api",
        "movies": movies,
    }
    if error:
        payload["error"] = error
    with open(CINEPLEX_OUTPUT, "w") as f:
        json.dump(payload, f, indent=2)


def _removeOrphanPosters(keptFiles):
    if not os.path.isdir(STATIC_POSTERS_DIR):
        return
    removed = 0
    for filename in os.listdir(STATIC_POSTERS_DIR):
        if filename in keptFiles:
            continue
        filepath = os.path.join(STATIC_POSTERS_DIR, filename)
        try:
            if os.path.isfile(filepath):
                os.remove(filepath)
                removed += 1
        except OSError as e:
            print(f"[cineplex] Failed to remove {filepath}: {e}")
    if removed:
        print(f"[cineplex] Removed {removed} orphaned poster(s)")


if __name__ == "__main__":
    scrapeAnimeMovies()
