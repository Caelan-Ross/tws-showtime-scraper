# Movie Schedule Scraper

A Python scraper and local web UI for tracking IMAX showtimes at TELUS World of Science Edmonton and anime releases at Cineplex theatres. Sends a weekly email digest, exposes a self-hosted dashboard, and caches poster images locally.

---

## Overview

Two scrapers run on a weekly schedule:

| Source | Method | Output |
|---|---|---|
| TELUS World of Science (TWS) | Vantix API direct | IMAX showtimes for the next two weekends |
| Cineplex Film Series page | HTML scrape (BeautifulSoup) | Upcoming and current anime movies |

Results are saved to JSON, emailed as a combined HTML digest every Monday morning, and rendered on a local web dashboard with poster art.

---

## Features

- Weekly email digest combining both sources
- Local web UI at `http://<host>:5000` with card-based layout
- On-demand refresh button — triggers both scrapers from the browser
- Poster images cached locally, orphans cleaned up on each run
- Modular: scrapers, email builder, and web UI run independently

---

## Requirements

- Python 3.10+
- A Gmail account with an app password
- Pip packages: `requests`, `beautifulsoup4`, `flask`

---

## Installation

### 1. Clone the repo

```bash
git clone git@github.com:Caelan-Ross/tws-showtime-scraper.git
cd tws-showtime-scraper
```

### 2. Install dependencies

```bash
pip3 install requests beautifulsoup4 flask --break-system-packages
```

### 3. Create the config file

Create `config.py` in the project root (excluded from version control):

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

### Run everything (scrapers + email)

```bash
python3 main.py
```

This runs both scrapers, writes JSON output, and sends the email digest.

### Run individual scrapers

```bash
python3 tws_scraper.py        # TWS IMAX only
python3 cineplex_scraper.py   # Cineplex anime only
```

### Run the web UI

```bash
python3 web.py
```

Then browse to `http://<host>:5000`.

---

## Scheduling

Add a cron job to run every Monday at 8am:

```bash
crontab -e
```

```
0 8 * * 1 cd /opt/imax-scraper && python3 main.py >> /var/log/imax-scraper.log 2>&1
```

The `cd` matters — Python needs the working directory to find sibling modules.

### Web UI as a systemd service

Create `/etc/systemd/system/movie-web.service`:

```ini
[Unit]
Description=Movie Schedule Web UI
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/imax-scraper
ExecStart=/usr/bin/python3 /opt/imax-scraper/web.py
Restart=on-failure
RestartSec=5
StandardOutput=append:/var/log/movie-web.log
StandardError=append:/var/log/movie-web.log

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
systemctl daemon-reload
systemctl enable --now movie-web
```

---

## Output

### TWS JSON — `/data/showtimes.json`

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

### Cineplex anime JSON — `/data/cineplex_anime.json`

```json
{
  "scraped_at": "2026-04-29T08:00:00",
  "movies": [
    {
      "title": "Attack on Titan: THE LAST ATTACK (Japanese w/ e.s.t)",
      "status": "Coming Soon",
      "release_date": "Sunday, May 17, 2026",
      "poster_url": "https://www.cineplex.com/_next/image?url=...",
      "detail_url": "https://www.cineplex.com/movie/attack-on-titan-the-last-attack-japanese-w-es",
      "local_poster": "posters/attack-on-titan-the-last-attack-japanese-w-e-s-t.jpg"
    }
  ]
}
```

### Email digest

Combined HTML email with TWS showtimes (current weekend, non-General films) and the full Cineplex anime listing. Posters embedded inline as CID attachments so they render even without external image loading.

### Web dashboard

Single-page dark-themed UI:

- TWS section: day-by-day cards with title, rating, duration, and showtimes
- Cineplex section: poster grid with title, status, and release date
- Refresh button: triggers both scrapers as subprocesses, reloads on success

---

## Project Structure

```
tws-showtime-scraper/
├── main.py                  # Orchestrator — runs scrapers + email
├── tws_scraper.py           # TWS IMAX scraper
├── cineplex_scraper.py      # Cineplex anime scraper
├── email_builder.py         # Combined HTML email + sender
├── web.py                   # Flask web UI
├── config.py                # Credentials (not committed)
├── templates/
│   └── index.html
├── static/
│   ├── style.css
│   ├── app.js
│   └── posters/             # Cached anime posters (not committed)
├── .gitignore
└── README.md
```

---

## API and Scraping Details

### TWS — Vantix API

```
GET https://www.onlinebookings.edmontonscience.com/api/schedules?tagId=64&start=YYYY-MM-DD
```

No authentication. `Referer` and `X-Requested-With` headers match expected browser behaviour.

### Cineplex — Film Series page

```
GET https://www.cineplex.com/events/film-series
```

The page is server-rendered (Next.js SSR), so a plain HTTP fetch + BeautifulSoup parse works without a headless browser. Anime listings are always under subcategory index `0`. Posters are pulled from the underlying `mediafiles.cineplex.com` URLs (extracted from the `_next/image` proxy params) to bypass the proxy's whitelisted-width restrictions.

---

## Notes

- General-rated films are filtered out of the TWS email digest but kept in the JSON snapshot.
- Films with the same `itemId` across multiple time slots are merged into a single entry with a list of showtimes.
- Cineplex poster cache uses orphan cleanup — files for movies no longer on the page are removed on each scrape. Files for movies still listed are skipped (not re-downloaded) for speed.
- The scraper runs bare Python on the host, no Docker required.
- Web UI listens on `0.0.0.0:5000` for LAN access. Pair with local DNS (e.g. `movie-scraper.home.arpa` via Pi-hole) for clean URLs.

---

## Optional: Local DNS and Homepage integration

Add a Pi-hole local DNS record:

```
movie-scraper.home.arpa → <lxc-ip>
```

Then add to your Homepage `services.yaml`:

```yaml
- Movie Scraper:
    href: http://movie-scraper.home.arpa:5000
    description: Local IMAX + Cineplex anime listings
    icon: mdi-movie-open
    siteMonitor: http://movie-scraper.home.arpa:5000
```