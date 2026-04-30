"""TELUS World of Science IMAX showtime scraper."""

import requests
import json
from datetime import datetime, timedelta

API_URL = "https://www.onlinebookings.edmontonscience.com/api/schedules"
TAG_ID = 64
OUTPUT = "/data/showtimes.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0",
    "Accept": "*/*",
    "Referer": "https://www.onlinebookings.edmontonscience.com/imaxcalendar.aspx",
    "X-Requested-With": "XMLHttpRequest",
}


def get_target_dates():
    today = datetime.today()
    monday = today - timedelta(days=today.weekday())
    dates = []
    for week_offset in [0, 1]:
        friday = monday + timedelta(days=4 + (week_offset * 7))
        dates += [friday, friday + timedelta(days=1), friday + timedelta(days=2)]
    return dates


def fetch_schedule(date_str):
    r = requests.get(
        API_URL,
        params={"tagId": TAG_ID, "start": date_str},
        headers=HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def scrape():
    results = {}
    for date in get_target_dates():
        date_str = date.strftime("%Y-%m-%d")
        label = date.strftime("%A %B %-d, %Y")
        try:
            data = fetch_schedule(date_str)
            merged = {}
            for e in data:
                item_id = e["itemId"]
                time = e.get("formattedStartTime")
                if item_id not in merged:
                    merged[item_id] = {
                        "title": e.get("name"),
                        "rating": e.get("eventRating"),
                        "duration": e.get("duration"),
                        "showtimes": [],
                        "item_url": "https:" + e["itemUrl"],
                    }
                if time:
                    merged[item_id]["showtimes"].append(time)
            results[date_str] = {
                "label": label,
                "films": list(merged.values()),
            }
        except Exception as ex:
            print(f"[imax] Failed for {date_str}: {ex}")
            results[date_str] = {"label": label, "films": [], "error": str(ex)}

    with open(OUTPUT, "w") as f:
        json.dump(
            {"scraped_at": datetime.now().isoformat(), "schedule": results},
            f,
            indent=2,
        )

    total = sum(len(v["films"]) for v in results.values())
    print(f"[imax] Done — {total} unique films across {len(results)} days")
    return results


if __name__ == "__main__":
    scrape()