"""Builds and sends the combined weekly digest email."""

import os
import smtplib
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from constants import GMAIL_USER, GMAIL_APP_PASSWORD, EMAIL_TO, CINEPLEX_IMAGE_HEADERS, STATIC_POSTERS_DIR


def _readLocalPoster(localPath):
    """Returns (bytes, mime_subtype) from a local poster path, or (None, None)."""
    if not localPath:
        return None, None
    absPath = os.path.join(os.path.dirname(STATIC_POSTERS_DIR), localPath)
    if not os.path.isfile(absPath):
        return None, None
    ext = os.path.splitext(absPath)[1].lstrip(".").lower() or "jpg"
    if ext == "jpeg":
        ext = "jpg"
    try:
        with open(absPath, "rb") as fileHandle:
            return fileHandle.read(), ext
    except OSError:
        return None, None


def _fetchImage(url):
    """Returns (bytes, mime_subtype) or (None, None) on failure."""
    try:
        r = requests.get(url, headers=CINEPLEX_IMAGE_HEADERS, timeout=15)
        r.raise_for_status()
        contentType = r.headers.get("Content-Type", "image/jpeg")
        subtype = contentType.split("/")[-1].split(";")[0].strip() or "jpeg"
        return r.content, subtype
    except requests.RequestException as e:
        print(f"[email] Image fetch failed for {url}: {e}")
        return None, None


def _buildImaxSection(imaxResults):
    if not imaxResults:
        return """
        <tr>
            <td colspan="3" style="padding:16px;color:#999;">
                No IMAX data available.
            </td>
        </tr>"""

    rows = ""
    for dateStr, day in imaxResults.items():
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


def _buildAnimeSection(animeMovies, cidPrefix="poster"):
    """Returns (html_rows, [(cid, image_bytes, subtype), ...])."""
    if not animeMovies:
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

    for idx, movie in enumerate(animeMovies):
        posterHtml = ""
        imgBytes, subtype = _readLocalPoster(movie.get("local_poster"))
        if not imgBytes:
            imgBytes, subtype = _fetchImage(movie.get("poster_url"))
        if imgBytes:
            cid = f"{cidPrefix}_{idx}"
            images.append((cid, imgBytes, subtype))
            posterHtml = (
                f'<img src="cid:{cid}" alt="" width="80" '
                f'style="display:block;border-radius:4px;">'
            )

        status = movie.get("status") or ""
        release = movie.get("release_date") or ""
        showtimes = movie.get("showtimes") or []
        detailUrl = movie.get("detail_url") or "#"

        showtimeHtml = ""
        if showtimes:
            showtimeHtml = f'<div style="color:#ccc;font-size:12px;margin-top:4px;">{" · ".join(showtimes)}</div>'

        rows += f"""
        <tr style="border-bottom:1px solid #2a2a3e;">
            <td style="padding:12px 16px;width:96px;vertical-align:top;">
                {posterHtml}
            </td>
            <td style="padding:12px 16px;vertical-align:top;">
                <a href="{detailUrl}" style="color:#7eb8f7;text-decoration:none;font-weight:600;font-size:15px;">{movie['title']}</a>
                <div style="color:#aaa;font-size:13px;margin-top:4px;">{status}</div>
                <div style="color:#888;font-size:12px;margin-top:2px;">{release}</div>
                {showtimeHtml}
            </td>
        </tr>"""

    return rows, images


def buildEmailHtml(imaxResults, cineplexMovies, landmarkMovies):
    """Returns (html, [(cid, image_bytes, subtype), ...])."""
    imaxRows = _buildImaxSection(imaxResults)
    cineplexRows, cineplexImages = _buildAnimeSection(cineplexMovies, cidPrefix="cpx")
    landmarkRows, landmarkImages = _buildAnimeSection(landmarkMovies, cidPrefix="lmk")

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
                                {imaxRows}
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
                            <h2 style="margin:0;color:#fff;font-size:18px;">Landmark Cinemas Anime</h2>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:8px 0 16px;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                {landmarkRows}
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:0 32px 16px;">
                            <a href="https://www.atomtickets.com/theaters/landmark-cinemas-8-st-albert/47654" style="color:#7eb8f7;font-size:13px;">View Landmark Cinemas showtimes →</a>
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
                                {cineplexRows}
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

    return html, cineplexImages + landmarkImages


def sendEmail(imaxResults, cineplexMovies, landmarkMovies):
    thisWeekImax = dict(list(imaxResults.items())[:3]) if imaxResults else {}

    html, images = buildEmailHtml(thisWeekImax, cineplexMovies, landmarkMovies)

    recipients = [addr.strip() for addr in EMAIL_TO.split(",") if addr.strip()]

    msg = MIMEMultipart("related")
    msg["Subject"] = f"Movie Digest — {datetime.now().strftime('%B %-d, %Y')}"
    msg["From"] = GMAIL_USER
    msg["To"] = ", ".join(recipients)

    alt = MIMEMultipart("alternative")
    msg.attach(alt)
    alt.attach(MIMEText(html, "html"))

    for cid, imgBytes, subtype in images:
        imgPart = MIMEImage(imgBytes, _subtype=subtype)
        imgPart.add_header("Content-ID", f"<{cid}>")
        imgPart.add_header("Content-Disposition", "inline", filename=f"{cid}.{subtype}")
        msg.attach(imgPart)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, recipients, msg.as_string())

    print(f"[email] Sent with {len(images)} inline images.")
