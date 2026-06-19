"""Orchestrator — runs all scrapers and sends the digest email."""

import re
import json
from datetime import datetime
import tws_scraper
import cineplex_scraper
import landmark_scraper
import email_builder
from constants import CINEPLEX_OUTPUT


def _normalizeTitle(title):
    cleaned = re.sub(r"\s*\([^)]*\)\s*", " ", title).strip()
    return re.sub(r"[^a-z0-9]", "", cleaned.lower())


def _writeCineplexFiltered(movies):
    """Overwrite CINEPLEX_OUTPUT with the post-deduplication list so the web UI stays consistent."""
    try:
        with open(CINEPLEX_OUTPUT) as fileHandle:
            payload = json.load(fileHandle)
    except (OSError, json.JSONDecodeError):
        payload = {"source": "cineplex-api"}
    payload["movies"] = movies
    payload["deduplicated_at"] = datetime.now().isoformat()
    with open(CINEPLEX_OUTPUT, "w") as fileHandle:
        json.dump(payload, fileHandle, indent=2)


def main():
    try:
        twsResults = tws_scraper.scrape()
    except Exception as e:
        print(f"[main] TWS scraper crashed: {e}")
        twsResults = {}

    try:
        cineplexMovies = cineplex_scraper.scrapeAnimeMovies()
    except Exception as e:
        print(f"[main] Cineplex scraper crashed: {e}")
        cineplexMovies = []

    try:
        # Run Landmark without exclusions so it writes its full list to disk
        landmarkMovies = landmark_scraper.scrapeAnimeMovies()
    except Exception as e:
        print(f"[main] Landmark scraper crashed: {e}")
        landmarkMovies = []

    # Prefer Landmark: drop from Cineplex any title already covered there
    landmarkTitles = {_normalizeTitle(m["title"]) for m in landmarkMovies}
    cineplexMovies = [m for m in cineplexMovies if _normalizeTitle(m["title"]) not in landmarkTitles]
    _writeCineplexFiltered(cineplexMovies)
    print(f"[main] Cineplex after dedup: {len(cineplexMovies)} movies")

    try:
        email_builder.sendEmail(twsResults, cineplexMovies, landmarkMovies)
    except Exception as e:
        print(f"[main] Email failed: {e}")


if __name__ == "__main__":
    main()
