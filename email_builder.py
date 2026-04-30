"""Builds and sends the combined weekly digest email."""

import smtplib
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from config import GMAIL_USER, GMAIL_APP_PASSWORD, EMAIL_TO

IMAGE_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.cineplex.com/",
}


def _fetch_image(url):
    """Returns (bytes, mime_subtype) or (None, None) on failure."""
    try:
        r = requests.get(url, headers=IMAGE_FETCH_HEADERS, timeout=15)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "image/jpeg")
        subtype = content_type.split("/")[-1].split(";")[0].strip() or "jpeg"
        return r.content, subtype
    except requests.RequestException as e:
        print(f"[email] Image fetch failed for {url}: {e}")
        return None, None


def _build_imax_section(imax_results):
    if not imax_results:
        return """
        <tr>
            <td colspan="3" style="padding:16px;color:#999;">
                No IMAX data available.
            </td>
        </tr>"""

    rows = ""
    for date_str, day in imax_results.items():
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
    return rows


def _build_anime_section(anime_movies):
    """Returns (html_rows, [(cid, image_bytes, subtype), ...])."""
    if not anime_movies:
        return (
            """
        <tr>
            <td colspan="2" style="padding:16px;color:#999;">
                No anime listings found.
            </td>
        </tr>""",
            [],
        )

    rows = ""
    images = []

    for idx, movie in enumerate(anime_movies):
        poster_html = ""
        poster_url = movie.get("poster_url")

        if poster_url:
            img_bytes, subtype = _fetch_image(poster_url)
            if img_bytes:
                cid = f"poster_{idx}"
                images.append((cid, img_bytes, subtype))
                poster_html = (
                    f'<img src="cid:{cid}" alt="" width="80" '
                    f'style="display:block;border-radius:4px;">'
                )

        status = movie.get("status") or ""
        release = movie.get("release_date") or ""
        detail_url = movie.get("detail_url") or "#"

        rows += f"""
        <tr style="border-bottom:1px solid #2a2a3e;">
            <td style="padding:12px 16px;width:96px;vertical-align:top;">
                {poster_html}
            </td>
            <td style="padding:12px 16px;vertical-align:top;">
                <a href="{detail_url}" style="color:#7eb8f7;text-decoration:none;font-weight:600;font-size:15px;">{movie['title']}</a>
                <div style="color:#aaa;font-size:13px;margin-top:4px;">{status}</div>
                <div style="color:#888;font-size:12px;margin-top:2px;">{release}</div>
            </td>
        </tr>"""

    return rows, images


def build_email_html(imax_results, anime_movies):
    """Returns (html, [(cid, image_bytes, subtype), ...])."""
    imax_rows = _build_imax_section(imax_results)
    anime_rows, anime_images = _build_anime_section(anime_movies)

    html = f"""
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
                            <h1 style="margin:0;color:#fff;font-size:22px;">🎬 Weekly Movie Digest</h1>
                            <p style="margin:6px 0 0;color:#aaa;font-size:14px;">Generated {datetime.now().strftime("%B %-d, %Y")}</p>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding:24px 32px 8px;">
                            <h2 style="margin:0;color:#fff;font-size:18px;">TELUS World of Science IMAX</h2>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:8px 0 16px;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                {imax_rows}
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:0 32px 16px;">
                            <a href="https://www.onlinebookings.edmontonscience.com/imaxcalendar.aspx" style="color:#7eb8f7;font-size:13px;">View full IMAX calendar →</a>
                        </td>
                    </tr>

                    <tr><td style="border-top:1px solid #2a2a3e;height:1px;"></td></tr>

                    <tr>
                        <td style="padding:24px 32px 8px;">
                            <h2 style="margin:0;color:#fff;font-size:18px;">Cineplex Anime</h2>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:8px 0 16px;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                {anime_rows}
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:0 32px 24px;">
                            <a href="https://www.cineplex.com/events/film-series" style="color:#7eb8f7;font-size:13px;">View Cineplex Film Series →</a>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    return html, anime_images


def send_email(imax_results, anime_movies):
    this_week_imax = dict(list(imax_results.items())[:3]) if imax_results else {}

    html, images = build_email_html(this_week_imax, anime_movies)

    # 'related' wraps HTML + inline images so cid: refs resolve
    msg = MIMEMultipart("related")
    msg["Subject"] = f"Movie Digest — {datetime.now().strftime('%B %-d, %Y')}"
    msg["From"] = GMAIL_USER
    msg["To"] = EMAIL_TO

    # 'alternative' lets clients pick HTML (we only provide HTML here)
    alt = MIMEMultipart("alternative")
    msg.attach(alt)
    alt.attach(MIMEText(html, "html"))

    # Attach inline images
    for cid, img_bytes, subtype in images:
        img_part = MIMEImage(img_bytes, _subtype=subtype)
        img_part.add_header("Content-ID", f"<{cid}>")
        img_part.add_header("Content-Disposition", "inline", filename=f"{cid}.{subtype}")
        msg.attach(img_part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, EMAIL_TO, msg.as_string())

    print(f"[email] Sent with {len(images)} inline images.")