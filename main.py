"""Orchestrator — runs all scrapers and sends the digest email."""

import tws_scraper
import cineplex_scraper
import email_builder


def main():
    # Run scrapers — failures in one shouldn't block the others
    try:
        tws_results = tws_scraper.scrape()
    except Exception as e:
        print(f"[main] TWS scraper crashed: {e}")
        tws_results = {}

    try:
        anime_movies = cineplex_scraper.scrape_anime_movies()
    except Exception as e:
        print(f"[main] Cineplex scraper crashed: {e}")
        anime_movies = []

    # Send combined email
    try:
        email_builder.send_email(tws_results, anime_movies)
    except Exception as e:
        print(f"[main] Email failed: {e}")


if __name__ == "__main__":
    main()