"""Fetches anime/Japanese-language movies from the Cineplex theatrical API.

Replaces the old HTML scraper with a direct API call.
Posters are downloaded to STATIC_POSTERS_DIR for local serving.
"""

import os
import re
import requests
import json
from datetime import datetime
from urllib.parse import urlparse, parse_qs, unquote

ANILIST_URL = "https://graphql.anilist.co"
_anilist_cache = {}  # title -> bool

API_URL = "https://apis.cineplex.com/prod/cpx/theatrical/api/v1/movies"
API_KEY = "dcdac5601d864addbc2675a2e96cb1f8"
OUTPUT = "/data/cineplex_anime.json"
STATIC_POSTERS_DIR = "/opt/imax-scraper/static/posters"

API_HEADERS = {
    "Ocp-Apim-Subscription-Key": API_KEY,
    "Origin": "https://www.cineplex.com",
    "Referer": "https://www.cineplex.com/",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

IMAGE_HEADERS = {
    "User-Agent": API_HEADERS["User-Agent"],
    "Referer": "https://www.cineplex.com/",
}

TAKE = 200  # grab everything in one request


def _strip_qualifiers(title):
    """Remove trailing parentheticals like '(Japanese w/e.s.t)' for cleaner lookups."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()


def _in_anilist(title):
    """Return True if AniList recognises the title as anime. Results are cached."""
    cleaned = _strip_qualifiers(title)
    if cleaned in _anilist_cache:
        return _anilist_cache[cleaned]

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

    _anilist_cache[cleaned] = found
    return found


def _is_anime(movie):
    """Match anime by genre tag, title keyword, or AniList lookup."""
    genres = movie.get("genres") or []
    name = movie.get("name") or ""
    if "Anime" in genres or "anime" in name.lower():
        return True
    if "japanese" in name.lower():
        return _in_anilist(name)
    return False


def scrape_anime_movies():
    try:
        resp = requests.get(
            API_URL,
            params={
                "language": "en-us",
                "skip": 0,
                "take": TAKE,
                "filterEvents": "false",
                "removeIrrelevantFilms": "true",
            },
            headers=API_HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[cineplex] API fetch failed: {e}")
        _write_output([], error=str(e))
        return []

    all_movies = data.get("items", [])
    anime = [m for m in all_movies if _is_anime(m)]
    anime.sort(key=lambda m: m.get("releaseDate") or "9999")

    os.makedirs(STATIC_POSTERS_DIR, exist_ok=True)
    kept_files = set()
    results = []

    for movie in anime:
        poster_url = movie.get("mediumPosterImageUrl")
        title = movie["name"]
        local_path = _download_poster(title, poster_url)

        entry = {
            "title": title,
            "status": _status_label(movie),
            "release_date": _format_date(movie.get("releaseDate")),
            "poster_url": poster_url,
            "detail_url": movie.get("detailPageUrl"),
            "local_poster": local_path,
            "genres": movie.get("genres", []),
            "language": movie.get("language"),
            "runtime": movie.get("runtimeInMinutes"),
        }

        if local_path:
            kept_files.add(os.path.basename(local_path))
        results.append(entry)

    _remove_orphan_posters(kept_files)
    _write_output(results)
    print(f"[cineplex] Done — {len(results)} anime movies (from {len(all_movies)} total)")
    return results


def _status_label(movie):
    if movie.get("isNowPlaying"):
        return "Now Playing"
    if movie.get("isComingSoon"):
        return "Coming Soon"
    return None


def _format_date(date_str):
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%B %-d, %Y")
    except (ValueError, AttributeError):
        return date_str


def _slugify(text):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug[:60] or "poster"


def _download_poster(title, url):
    if not url:
        return None

    slug = _slugify(title)

    # Skip download if we already have this poster
    for existing in os.listdir(STATIC_POSTERS_DIR):
        if existing.startswith(f"{slug}."):
            return f"posters/{existing}"

    filepath = os.path.join(STATIC_POSTERS_DIR, f"{slug}.jpg")

    try:
        r = requests.get(url, headers=IMAGE_HEADERS, timeout=15)
        r.raise_for_status()

        ct = r.headers.get("Content-Type", "image/jpeg")
        ext = ct.split("/")[-1].split(";")[0].strip()
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


def _write_output(movies, error=None):
    payload = {
        "scraped_at": datetime.now().isoformat(),
        "source": "cineplex-api",
        "movies": movies,
    }
    if error:
        payload["error"] = error
    with open(OUTPUT, "w") as f:
        json.dump(payload, f, indent=2)


def _remove_orphan_posters(kept_files):
    if not os.path.isdir(STATIC_POSTERS_DIR):
        return
    removed = 0
    for filename in os.listdir(STATIC_POSTERS_DIR):
        if filename in kept_files:
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
    scrape_anime_movies()