"""Scrapes anime movies from Atom Tickets for Landmark Cinemas 8 St. Albert.

Combines current showtimes and coming soon into a single unified list,
cross-validates against AniList, and downloads posters locally.
"""

import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from constants import (
    ATOMTICKETS_BASE_URL,
    ATOMTICKETS_THEATER_URL,
    ATOMTICKETS_COMING_SOON_URL,
    ATOMTICKETS_OUTPUT,
    ATOMTICKETS_HEADERS,
    ANILIST_URL,
    STATIC_POSTERS_DIR,
)

_anilistCache = {}
_ACCEPTED_FORMATS = {"MOVIE", "TV", "SPECIAL"}
_TITLE_STOP_WORDS = {"the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or"}


def _stripQualifiers(title):
    return re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()


def _titleKeyWords(title):
    if not title:
        return set()
    tokens = re.sub(r"[^a-z0-9\s]", "", title.lower()).split()
    return {t for t in tokens if t not in _TITLE_STOP_WORDS and len(t) >= 3}


def _jaccard(wordsA, wordsB):
    if not wordsA or not wordsB:
        return 0.0
    return len(wordsA & wordsB) / len(wordsA | wordsB)


def _titlesSimilar(searchTitle, foundEnglish, foundRomaji):
    """Return True if the AniList result title is close enough to the search term.

    Checks English title first (Jaccard >= 0.6), then falls back to romaji
    (Jaccard >= 0.3). Rejects when neither title provides sufficient overlap.
    """
    searchWords = _titleKeyWords(searchTitle)
    if not searchWords:
        return False

    if foundEnglish:
        return _jaccard(searchWords, _titleKeyWords(foundEnglish)) >= 0.6

    if foundRomaji:
        return _jaccard(searchWords, _titleKeyWords(foundRomaji)) >= 0.3

    return False


def _inAnilist(title):
    cleaned = _stripQualifiers(title)
    if cleaned in _anilistCache:
        return _anilistCache[cleaned]

    query = """
    query ($search: String) {
      Media(search: $search, type: ANIME) { id format title { english romaji } }
    }
    """
    try:
        resp = requests.post(
            ANILIST_URL,
            json={"query": query, "variables": {"search": cleaned}},
            timeout=10,
        )
        media = resp.json().get("data", {}).get("Media")
        if media is None:
            found = False
        else:
            mediaFormat = media.get("format") or ""
            titles = media.get("title") or {}
            found = (
                mediaFormat in _ACCEPTED_FORMATS
                and _titlesSimilar(cleaned, titles.get("english"), titles.get("romaji"))
            )
    except Exception:
        found = False

    _anilistCache[cleaned] = found
    time.sleep(0.8)
    return found


def _normalizeTitle(title):
    cleaned = re.sub(r"\s*\([^)]*\)\s*", " ", title).strip()
    return re.sub(r"[^a-z0-9]", "", cleaned.lower())


def _scalePosterUrl(url):
    """Upscale Cloudinary poster from thumbnail to 320x470."""
    if not url or "cloudinary" not in url:
        return url
    return re.sub(r"h_\d+,q_auto,w_\d+", "h_470,q_auto,w_320", url)


def _slugify(text):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return "atom-" + (slug[:55] or "poster")


def _downloadPoster(title, url):
    if not url:
        return None

    slug = _slugify(title)

    for existing in os.listdir(STATIC_POSTERS_DIR):
        if existing.startswith(f"{slug}."):
            return f"posters/{existing}"

    try:
        r = requests.get(url, headers=ATOMTICKETS_HEADERS, timeout=15)
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
        print(f"[atom] Poster download failed for {title}: {e}")
        return None


def _fetchHtml(url):
    resp = requests.get(url, headers=ATOMTICKETS_HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def _parseProductionId(href):
    match = re.search(r"/(\d+)(?:\?|$)", href or "")
    return match.group(1) if match else None


def _formatDate(dateStr):
    if not dateStr:
        return None
    try:
        dt = datetime.fromisoformat(dateStr)
        return dt.strftime("%B %-d, %Y")
    except (ValueError, AttributeError):
        return dateStr


def _parseCurrentShowtimes(soup):
    """Parse movies currently playing from the theater page."""
    movies = {}
    for panel in soup.find_all("div", class_="showtime-panel"):
        titleEl = panel.find("h2", class_="production-row__title")
        if not titleEl:
            continue
        link = titleEl.find("a")
        if not link:
            continue

        title = link.get_text(strip=True)
        href = link.get("href", "")
        productionId = _parseProductionId(href)
        detailUrl = ATOMTICKETS_BASE_URL + href if href.startswith("/") else href

        imgEl = panel.find("img", class_="poster")
        rawPosterUrl = imgEl.get("data-src") if imgEl else None
        posterUrl = _scalePosterUrl(rawPosterUrl)

        showtimes = []
        for btn in panel.find_all("a", class_="btn-showtime"):
            if "preorder" in (btn.get("class") or []):
                continue
            btnText = btn.get_text(strip=True)
            # Only keep entries that look like a time (e.g. "7:00 PM", "10:15 AM")
            if btnText and re.match(r"^\d{1,2}:\d{2}\s*(AM|PM)$", btnText, re.IGNORECASE):
                if btnText not in showtimes:
                    showtimes.append(btnText)

        key = productionId or title
        if key not in movies:
            movies[key] = {
                "title": title,
                "status": "Now Playing",
                "release_date": None,
                "poster_url": posterUrl,
                "detail_url": detailUrl,
                "showtimes": showtimes,
                "production_id": productionId,
            }

    return movies


def _parseComingSoon(soup):
    """Parse coming soon movies from the coming soon page."""
    movies = {}
    for row in soup.find_all("div", class_="production-row"):
        titleEl = row.find("h2", class_="production-row__title")
        if not titleEl:
            continue
        link = titleEl.find("a")
        if not link:
            continue

        title = link.get_text(strip=True)
        href = link.get("href", "")
        productionId = _parseProductionId(href)
        detailUrl = ATOMTICKETS_BASE_URL + href if href.startswith("/") else href

        imgEl = row.find("img", class_="poster")
        rawPosterUrl = imgEl.get("data-src") if imgEl else None
        posterUrl = _scalePosterUrl(rawPosterUrl)

        releaseDate = None
        metaLink = row.find("a", attrs={"data-product-metadata": True})
        if metaLink:
            try:
                meta = json.loads(metaLink["data-product-metadata"])
                releaseDate = _formatDate(meta.get("releaseDate"))
            except (json.JSONDecodeError, KeyError):
                pass

        key = productionId or title
        if key not in movies:
            movies[key] = {
                "title": title,
                "status": "Coming Soon",
                "release_date": releaseDate,
                "poster_url": posterUrl,
                "detail_url": detailUrl,
                "showtimes": [],
                "production_id": productionId,
            }

    return movies


def _removeOrphanPosters(keptFiles):
    if not os.path.isdir(STATIC_POSTERS_DIR):
        return
    removed = 0
    for filename in os.listdir(STATIC_POSTERS_DIR):
        if not filename.startswith("atom-"):
            continue
        if filename in keptFiles:
            continue
        filepath = os.path.join(STATIC_POSTERS_DIR, filename)
        try:
            if os.path.isfile(filepath):
                os.remove(filepath)
                removed += 1
        except OSError as e:
            print(f"[atom] Failed to remove {filepath}: {e}")
    if removed:
        print(f"[atom] Removed {removed} orphaned poster(s)")


def _writeOutput(movies, error=None):
    payload = {
        "scraped_at": datetime.now().isoformat(),
        "source": "atomtickets-html",
        "movies": movies,
    }
    if error:
        payload["error"] = error
    with open(ATOMTICKETS_OUTPUT, "w") as fileHandle:
        json.dump(payload, fileHandle, indent=2)


def scrapeAnimeMovies(excludeTitles=None):
    """Scrape Landmark Cinemas anime listings from Atom Tickets.

    excludeTitles: set of normalized titles already covered by another source.
    Returns list of movie dicts.
    """
    normalizedExcludes = excludeTitles or set()

    try:
        theaterSoup = _fetchHtml(ATOMTICKETS_THEATER_URL)
        currentMovies = _parseCurrentShowtimes(theaterSoup)
    except requests.RequestException as e:
        print(f"[atom] Theater page fetch failed: {e}")
        currentMovies = {}

    try:
        comingSoonSoup = _fetchHtml(ATOMTICKETS_COMING_SOON_URL)
        comingSoonMovies = _parseComingSoon(comingSoonSoup)
    except requests.RequestException as e:
        print(f"[atom] Coming soon page fetch failed: {e}")
        comingSoonMovies = {}

    # Current showings take priority over coming-soon for the same production
    merged = {**comingSoonMovies, **currentMovies}

    os.makedirs(STATIC_POSTERS_DIR, exist_ok=True)
    keptFiles = set()
    results = []

    for movie in merged.values():
        title = movie["title"]
        if _normalizeTitle(title) in normalizedExcludes:
            print(f"[atom] Skipping '{title}' — already in Cineplex listing")
            continue
        if not _inAnilist(title):
            continue

        localPath = _downloadPoster(title, movie["poster_url"])
        if localPath:
            keptFiles.add(os.path.basename(localPath))

        results.append({**movie, "local_poster": localPath})

    results.sort(key=lambda m: (m["status"] != "Now Playing", m.get("release_date") or "9999"))

    _removeOrphanPosters(keptFiles)
    _writeOutput(results)
    print(f"[atom] Done — {len(results)} anime movies")
    return results


if __name__ == "__main__":
    scrapeAnimeMovies()
