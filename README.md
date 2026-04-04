# TWS Showtime Scraper

A lightweight Python scraper that pulls IMAX showtime data from the TELUS World of Science Edmonton booking system and sends a weekly HTML email digest.

---

## Overview

The TELUS World of Science Edmonton IMAX calendar is powered by the Vantix ticketing API. This scraper hits that API directly, aggregates showtimes by film, filters out General-rated documentaries, and emails a formatted digest every Monday morning covering the upcoming Friday, Saturday, and Sunday.

A full two-week JSON snapshot (both weekends) is also saved locally for reference.

---

## Requirements

- Python 3.10+
- `requests` library
- A Gmail account with an app password

---

## Installation

### 1. Clone the repo

```bash
git clone git@github.com:Caelan-Ross/tws-showtime-scraper.git
cd tws-showtime-scraper
```

### 2. Install dependencies

```bash
pip3 install requests --break-system-packages
```

### 3. Create the config file

Create `config.py` in the project root. This file is excluded from version control.

```python
GMAIL_USER = "you@gmail.com"
GMAIL_APP_PASSWORD = "your-app-password-here"
EMAIL_TO = "you@gmail.com"
```

To generate a Gmail app password:

1. Go to myaccount.google.com
2. Enable 2-Step Verification if not already on
3. Search "App passwords" and create one
4. Paste the 16-character password into `config.py`

### 4. Create the output directory

```bash
mkdir -p /data
```

---

## Usage

Run manually:

```bash
python3 scraper.py
```

This will:

1. Fetch showtimes for the current and following weekend (6 days total)
2. Save a full JSON snapshot to `/data/showtimes.json`
3. Send an HTML email covering this weekend only (Fri/Sat/Sun), excluding General-rated films

---

## Scheduling

Add a cron job to run every Monday at 8am:

```bash
crontab -e
```

```
0 8 * * 1 python3 /opt/imax-scraper/scraper.py >> /var/log/imax-scraper.log 2>&1
```

---

## Output

### JSON

Saved to `/data/showtimes.json` after each run:

```json
{
  "scraped_at": "2026-04-07T08:00:00",
  "schedule": {
    "2026-04-10": {
      "label": "Friday April 10, 2026",
      "films": [
        {
          "title": "The Godfather (1972)",
          "rating": "14A",
          "duration": "175 minutes",
          "showtimes": ["7:00 PM"],
          "item_url": "https://www.onlinebookings.edmontonscience.com/DateSelection.aspx?item=6723"
        }
      ]
    }
  }
}
```

### Email

A dark-themed HTML email listing each day's non-General films with title, rating, duration, showtimes, and a purchase link. Only the current weekend is included in the email.

---

## Project Structure

```
tws-showtime-scraper/
├── scraper.py       # Main scraper and email sender
├── config.py        # Credentials (not committed)
├── Dockerfile       # Unused, kept for reference
├── .gitignore
└── README.md
```

---

## API Details

The scraper targets the Vantix scheduling API used by the TELUS World of Science booking system:

```
GET https://www.onlinebookings.edmontonscience.com/api/schedules?tagId=64&start=YYYY-MM-DD
```

No authentication is required. The `Referer` and `X-Requested-With` headers are included to match expected browser behaviour.

---

## Notes

- General-rated films are filtered out of the email. They are still saved to the JSON snapshot.
- Films with the same `itemId` across multiple time slots are merged into a single entry with a list of showtimes.
- The scraper runs bare Python on the host, no Docker required.
