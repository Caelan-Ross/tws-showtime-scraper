from config import EMAIL_TO, GMAIL_APP_PASSWORD, GMAIL_USER  # gitignored

# --- Paths ---
CINEPLEX_OUTPUT = "/data/cineplex_anime.json"
SCRAPER_DIR = "/opt/imax-scraper"
STATIC_POSTERS_DIR = "/opt/imax-scraper/static/posters"
TWS_OUTPUT = "/data/showtimes.json"

# --- Cineplex ---
ANILIST_URL = "https://graphql.anilist.co"
CINEPLEX_API_KEY = "dcdac5601d864addbc2675a2e96cb1f8"  # must precede CINEPLEX_API_HEADERS
CINEPLEX_API_HEADERS = {
    "Ocp-Apim-Subscription-Key": CINEPLEX_API_KEY,
    "Origin": "https://www.cineplex.com",
    "Referer": "https://www.cineplex.com/",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}
CINEPLEX_API_URL = "https://apis.cineplex.com/prod/cpx/theatrical/api/v1/movies"
CINEPLEX_IMAGE_HEADERS = {
    "User-Agent": CINEPLEX_API_HEADERS["User-Agent"],
    "Referer": "https://www.cineplex.com/",
}
CINEPLEX_TAKE = 200

# --- TWS ---
TWS_API_URL = "https://www.onlinebookings.edmontonscience.com/api/schedules"
TWS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0",
    "Accept": "*/*",
    "Referer": "https://www.onlinebookings.edmontonscience.com/imaxcalendar.aspx",
    "X-Requested-With": "XMLHttpRequest",
}
TWS_MIN_RUNTIME_MINUTES = 60
TWS_SKIP_TERMS = (
    "Sensory Friendly Screening",
    "Private Screening",
    "School Group",
)
TWS_TAG_ID = 64
