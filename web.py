"""Local Flask web UI for the movie scraper."""

import json
import os
import subprocess
from datetime import datetime
from flask import Flask, render_template, jsonify
from constants import TWS_OUTPUT, CINEPLEX_OUTPUT, LANDMARK_OUTPUT, SCRAPER_DIR

app = Flask(__name__)


def _loadJson(path):
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
    twsData = _loadJson(TWS_OUTPUT) or {}
    cineplexData = _loadJson(CINEPLEX_OUTPUT) or {}
    landmarkData = _loadJson(LANDMARK_OUTPUT) or {}

    twsSchedule = twsData.get("schedule", {})
    twsThisWeek = dict(list(twsSchedule.items())[:3])

    return render_template(
        "index.html",
        tws_days=twsThisWeek,
        cineplex_movies=cineplexData.get("movies", []),
        landmark_movies=landmarkData.get("movies", []),
        tws_scraped_at=twsData.get("scraped_at"),
        cineplex_scraped_at=cineplexData.get("scraped_at"),
        landmark_scraped_at=landmarkData.get("scraped_at"),
        now=datetime.now(),
    )


@app.route("/refresh", methods=["POST"])
def refresh():
    """Trigger all scrapers. Returns JSON status."""
    results = {"tws": None, "cineplex": None, "landmark": None}

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

    try:
        subprocess.run(
            ["python3", "landmark_scraper.py"],
            cwd=SCRAPER_DIR,
            timeout=120,
            check=True,
            capture_output=True,
        )
        results["landmark"] = "ok"
    except subprocess.CalledProcessError as e:
        results["landmark"] = f"error: {e.stderr.decode()[:200]}"
    except subprocess.TimeoutExpired:
        results["landmark"] = "error: timeout"

    return jsonify(results)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
