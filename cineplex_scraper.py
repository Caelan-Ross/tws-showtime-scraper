"""Scrapes the Cineplex Film Series page for anime listings.

Anime is always subcategory 0. Posters indexed 0..MAX_POSTERS-1.
Posters are downloaded to STATIC_POSTERS_DIR for local serving.
"""

import os
import re
import requests
import json
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, unquote

CINEPLEX_URL = "https://www.cineplex.com/events/film-series"
SUBCATEGORY_INDEX = 0
MAX_POSTERS = 10
OUTPUT = "/data/cineplex_anime.json"
STATIC_POSTERS_DIR = "/opt/imax-scraper/static/posters"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-CA,en;q=0.9",
}

IMAGE_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Referer": "https://www.cineplex.com/",
}


def scrape_anime_movies():
    try:
        resp = requests.get(CINEPLEX_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[cineplex] Fetch failed: {e}")
        _write_output([], error=str(e))
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    movies = []
    kept_files = set()
    os.makedirs(STATIC_POSTERS_DIR, exist_ok=True)

    for i in range(MAX_POSTERS):
        prefix = f"event-subcategory-{SUBCATEGORY_INDEX}-poster-{i}"
        container = soup.find(attrs={"data-testid": prefix})
        if container is None:
            break

        movie = _parse_poster(container, prefix)
        if movie:
            local_path = _download_poster(movie["title"], movie.get("poster_url"))
            movie["local_poster"] = local_path
            if local_path:
                kept_files.add(os.path.basename(local_path))
            movies.append(movie)

    _remove_orphan_posters(kept_files)
    _write_output(movies)
    print(f"[cineplex] Done — {len(movies)} anime movies")
    return movies


def _parse_poster(container, prefix):
    title_tag = container.find(attrs={"data-testid": f"{prefix}-event-title"})
    title = title_tag.get_text(strip=True) if title_tag else None

    status_tag = container.find(
        attrs={"data-testid": f"{prefix}-showtime-availability"}
    )
    status = status_tag.get_text(strip=True) if status_tag else None

    date_tag = container.find(attrs={"data-testid": f"{prefix}-release-date"})
    release_date = date_tag.get_text(strip=True) if date_tag else None

    poster_url = None
    img_container = container.find(
        "div",
        class_=lambda c: c and c.startswith("MoviePosterImage_imageContainer"),
    )
    if img_container:
        img = img_container.find("img")
        if img:
            src = img.get("src")
            if src:
                poster_url = (
                    src if src.startswith("http") else f"https://www.cineplex.com{src}"
                )

    detail_url = None
    link = container.find(
        "a", class_=lambda c: c and "MoviePosterImage_linkContainer" in c
    )
    if link and link.get("href"):
        href = link["href"]
        detail_url = href if href.startswith("http") else f"https://www.cineplex.com{href}"

    if not title:
        return None

    return {
        "title": title,
        "status": status,
        "release_date": release_date,
        "poster_url": poster_url,
        "detail_url": detail_url,
    }


def _slugify(text):
    """Convert a title to a safe filename."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug[:60] or "poster"


def _download_poster(title, url):
    if not url:
        return None

    parsed = urlparse(url)
    if parsed.path == "/_next/image":
        qs = parse_qs(parsed.query)
        real_url = qs.get("url", [None])[0]
        if real_url:
            url = unquote(real_url)

    slug = _slugify(title)

    # Check if any existing file matches this slug — skip download if so
    for existing in os.listdir(STATIC_POSTERS_DIR):
        if existing.startswith(f"{slug}."):
            return f"posters/{existing}"

    filename = f"{slug}.jpg"
    filepath = os.path.join(STATIC_POSTERS_DIR, filename)

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
        "movies": movies,
    }
    if error:
        payload["error"] = error
    with open(OUTPUT, "w") as f:
        json.dump(payload, f, indent=2)

def _remove_orphan_posters(kept_files):
    """Remove poster files not in the current scrape."""
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