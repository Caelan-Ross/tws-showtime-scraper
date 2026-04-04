import requests
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from config import GMAIL_USER, GMAIL_APP_PASSWORD, EMAIL_TO

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
        timeout=15
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
                "films": list(merged.values())
            }
        except Exception as ex:
            print(f"Failed for {date_str}: {ex}")
            results[date_str] = {"label": label, "films": [], "error": str(ex)}

    with open(OUTPUT, "w") as f:
        json.dump({"scraped_at": datetime.now().isoformat(), "schedule": results}, f, indent=2)

    total = sum(len(v["films"]) for v in results.values())
    print(f"Done — {total} unique films across {len(results)} days")
    return results

def build_email_html(results):
    rows = ""
    for date_str, day in results.items():
        rows += f"""
        <tr>
            <td colspan="3" style="background:#1a1a2e;color:#e0e0e0;padding:12px 16px;font-size:16px;font-weight:bold;border-radius:4px;">
                📅 {day['label']}
            </td>
        </tr>"""
        films = [f for f in day.get("films", []) if f["rating"] != "General"]
        if not films:
            rows += """
        <tr>
            <td colspan="3" style="padding:10px 16px;color:#999;">No non-General films scheduled.</td>
        </tr>"""
        for film in films:
            showtimes = " &nbsp;·&nbsp; ".join(film["showtimes"])
            rating = film["rating"] or "NR"
            rows += f"""
        <tr style="border-bottom:1px solid #2a2a3e;">
            <td style="padding:10px 16px;font-weight:600;color:#e0e0e0;">
                <a href="{film['item_url']}" style="color:#7eb8f7;text-decoration:none;">{film['title']}</a>
            </td>
            <td style="padding:10px 16px;color:#aaa;white-space:nowrap;">{rating} &nbsp;·&nbsp; {film['duration']}</td>
            <td style="padding:10px 16px;color:#ccc;">{showtimes}</td>
        </tr>"""
        rows += """
        <tr><td colspan="3" style="padding:6px;"></td></tr>"""

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#0f0f1a;font-family:Arial,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f0f1a;padding:32px 0;">
        <tr>
            <td align="center">
                <table width="640" cellpadding="0" cellspacing="0" style="background:#16162a;border-radius:8px;overflow:hidden;">
                    <tr>
                        <td style="background:#1a1a3e;padding:24px 32px;">
                            <h1 style="margin:0;color:#fff;font-size:22px;">🎬 TELUS World of Science IMAX</h1>
                            <p style="margin:6px 0 0;color:#aaa;font-size:14px;">Showtimes scraped {datetime.now().strftime("%B %-d, %Y")}</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:16px 0;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                {rows}
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:16px 32px;border-top:1px solid #2a2a3e;">
                            <a href="https://www.onlinebookings.edmontonscience.com/imaxcalendar.aspx"
                               style="color:#7eb8f7;font-size:13px;">View full calendar →</a>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

def send_email(results):
    this_week = dict(list(results.items())[:3])
    html = build_email_html(this_week)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"IMAX Showtimes — {datetime.now().strftime('%B %-d, %Y')}"
    msg["From"] = GMAIL_USER
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, EMAIL_TO, msg.as_string())

    print("Email sent.")

if __name__ == "__main__":
    results = scrape()
    send_email(results)
