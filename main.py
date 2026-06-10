"""Orchestrator — runs all scrapers and sends the digest email."""

import tws_scraper
import cineplex_scraper
import email_builder


def main():
    try:
        twsResults = tws_scraper.scrape()
    except Exception as e:
        print(f"[main] TWS scraper crashed: {e}")
        twsResults = {}

    try:
        animeMovies = cineplex_scraper.scrapeAnimeMovies()
    except Exception as e:
        print(f"[main] Cineplex scraper crashed: {e}")
        animeMovies = []

    try:
        email_builder.sendEmail(twsResults, animeMovies)
    except Exception as e:
        print(f"[main] Email failed: {e}")


if __name__ == "__main__":
    main()
