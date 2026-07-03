"""Tuning knobs and identifiers shared across the app."""

APP_NAME = "WebTunes Importer"
APP_AUTHOR = "matteob"

DEFAULT_SERVER_URL = "https://matteob.dev/projects/webtunes"

DEFAULT_STRICTNESS = 0.7  # match-score floor; user-adjustable 0..1 via the UI slider
DURATION_TOLERANCE = 15  # seconds
MIN_SOURCE_KBPS = 100  # drop tracks whose best available YouTube audio is below this
SEARCH_RESULTS = 10  # candidates to scan per track when matching
SEARCH_TAB_RESULTS = 25  # rows shown per query on the Search tab

RATE_LIMIT_COOLDOWN = 60  # seconds to pause after a YouTube 429 before retrying
MAX_RATE_LIMIT_RETRIES = 3  # cooldown+retry attempts before giving up on a 429

# (dropdown label, quality code passed to download_audio)
QUALITY_CHOICES = [
    ("128 kbps MP3", "128"),
    ("192 kbps MP3", "192"),
    ("Best (Opus, lossless)", "opus"),
    ("Best (.m4a, lossless)", "m4a"),
]

# WebTunes caps extension imports at 100 MB; check locally for a clearer error.
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
