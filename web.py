"""Local Flask web UI for the movie scraper."""

import json
import os
import subprocess
from datetime import datetime
from flask import Flask, render_template, jsonify

app = Flask(__name__)

tws_JSON = "/data/showtimes.json"
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
    tws_data = _load_json(tws_JSON) or {}
    anime_data = _load_json(ANIME_JSON) or {}

    tws_schedule = tws_data.get("schedule", {})
    # Only show current weekend in the web view (first 3 days)
    tws_this_week = dict(list(tws_schedule.items())[:3])

    anime_movies = anime_data.get("movies", [])

    return render_template(
        "index.html",
        tws_days=tws_this_week,
        anime_movies=anime_movies,
        tws_scraped_at=tws_data.get("scraped_at"),
        anime_scraped_at=anime_data.get("scraped_at"),
        now=datetime.now(),
    )


@app.route("/refresh", methods=["POST"])
def refresh():
    """Trigger both scrapers. Returns JSON status."""
    results = {"tws": None, "cineplex": None}

    try:
        subprocess.run(
            ["python3", "tws_scraper.py"],
            cwd=SCRAPER_DIR,
            timeout=120,
            check=True,
            capture_output=True,
        )
        results["tws"] = "ok"
    except subprocess.CalledProcessError as e:
        results["tws"] = f"error: {e.stderr.decode()[:200]}"
    except subprocess.TimeoutExpired:
        results["tws"] = "error: timeout"

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