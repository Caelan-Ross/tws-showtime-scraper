"""TELUS World of Science IMAX showtime scraper."""

import requests
import json
from datetime import datetime, timedelta
from constants import TWS_API_URL, TWS_TAG_ID, TWS_OUTPUT, TWS_MIN_RUNTIME_MINUTES, TWS_HEADERS, TWS_SKIP_TERMS


def _runtimeMinutes(durationStr):
    """Parse '45 minutes' → 45. Returns None if unparseable."""
    try:
        return int(str(durationStr).split()[0])
    except (ValueError, IndexError):
        return None


def getTargetDates():
    today = datetime.today()
    monday = today - timedelta(days=today.weekday())
    dates = []
    for weekOffset in [0, 1]:
        friday = monday + timedelta(days=4 + (weekOffset * 7))
        dates += [friday, friday + timedelta(days=1), friday + timedelta(days=2)]
    return dates


def fetchSchedule(dateStr):
    r = requests.get(
        TWS_API_URL,
        params={"tagId": TWS_TAG_ID, "start": dateStr},
        headers=TWS_HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def scrape():
    results = {}
    for date in getTargetDates():
        dateStr = date.strftime("%Y-%m-%d")
        label = date.strftime("%A %B %-d, %Y")
        try:
            data = fetchSchedule(dateStr)
            merged = {}
            for entry in data:
                name = entry.get("name", "")
                if any(p.lower() in name.lower() for p in TWS_SKIP_TERMS):
                    continue
                runtime = _runtimeMinutes(entry.get("duration"))
                if runtime is not None and runtime < TWS_MIN_RUNTIME_MINUTES:
                    continue
                itemId = entry["itemId"]
                time = entry.get("formattedStartTime")
                if itemId not in merged:
                    merged[itemId] = {
                        "title": entry.get("name"),
                        "rating": entry.get("eventRating"),
                        "duration": entry.get("duration"),
                        "showtimes": [],
                        "item_url": "https:" + entry["itemUrl"],
                    }
                if time:
                    merged[itemId]["showtimes"].append(time)
            results[dateStr] = {
                "label": label,
                "films": list(merged.values()),
            }
        except Exception as ex:
            print(f"[imax] Failed for {dateStr}: {ex}")
            results[dateStr] = {"label": label, "films": [], "error": str(ex)}

    with open(TWS_OUTPUT, "w") as f:
        json.dump(
            {"scraped_at": datetime.now().isoformat(), "schedule": results},
            f,
            indent=2,
        )

    total = sum(len(v["films"]) for v in results.values())
    print(f"[tws] Done — {total} unique films across {len(results)} days")
    return results


if __name__ == "__main__":
    scrape()
