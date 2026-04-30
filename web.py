"""Local Flask web UI for the movie scraper."""

import json
import os
import subprocess
from datetime import datetime
from flask import Flask, render_template, jsonify

app = Flask(__name__)

IMAX_JSON = "/data/showtimes.json"
ANIME_JSON = "/data/cineplex_anime.json"
SCRAPER_DIR = "/opt/imax-scraper"


def _load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[web] Failed to load {path}: {e}")
        return None


@app.route("/")
def index():
    imax_data = _load_json(IMAX_JSON) or {}
    anime_data = _load_json(ANIME_JSON) or {}

    imax_schedule = imax_data.get("schedule", {})
    # Only show current weekend in the web view (first 3 days)
    imax_this_week = dict(list(imax_schedule.items())[:3])

    anime_movies = anime_data.get("movies", [])

    return render_template(
        "index.html",
        imax_days=imax_this_week,
        anime_movies=anime_movies,
        imax_scraped_at=imax_data.get("scraped_at"),
        anime_scraped_at=anime_data.get("scraped_at"),
        now=datetime.now(),
    )


@app.route("/refresh", methods=["POST"])
def refresh():
    """Trigger both scrapers. Returns JSON status."""
    results = {"imax": None, "cineplex": None}

    try:
        subprocess.run(
            ["python3", "tws_scraper.py"],
            cwd=SCRAPER_DIR,
            timeout=120,
            check=True,
            capture_output=True,
        )
        results["imax"] = "ok"
    except subprocess.CalledProcessError as e:
        results["imax"] = f"error: {e.stderr.decode()[:200]}"
    except subprocess.TimeoutExpired:
        results["imax"] = "error: timeout"

    try:
        subprocess.run(
            ["python3", "cineplex_scraper.py"],
            cwd=SCRAPER_DIR,
            timeout=120,
            check=True,
            capture_output=True,
        )
        results["cineplex"] = "ok"
    except subprocess.CalledProcessError as e:
        results["cineplex"] = f"error: {e.stderr.decode()[:200]}"
    except subprocess.TimeoutExpired:
        results["cineplex"] = "error: timeout"

    return jsonify(results)


if __name__ == "__main__":
    # Listen on all interfaces so other machines on the LAN can reach it
    app.run(host="0.0.0.0", port=5000, debug=False)