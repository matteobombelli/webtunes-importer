"""YouTube 429 rate-limit handling: cooldown and retry."""

import time
from collections.abc import Callable

from webtunes_importer.constants import MAX_RATE_LIMIT_RETRIES, RATE_LIMIT_COOLDOWN


def _is_rate_limit(e):
    s = str(e).lower()
    return "429" in s or "too many requests" in s


def run_with_retry(log: Callable[[str], None], fn):
    """Run fn(), retrying after a cooldown on YouTube 429 rate-limits (capped at
    MAX_RATE_LIMIT_RETRIES). Any other exception - including a 403 - propagates
    to the caller, which logs it and moves on."""
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        try:
            return fn()
        except Exception as e:
            if _is_rate_limit(e) and attempt < MAX_RATE_LIMIT_RETRIES:
                log(f"YouTube rate-limiting (HTTP 429). Pausing {RATE_LIMIT_COOLDOWN}s, "
                    f"then retrying...")
                time.sleep(RATE_LIMIT_COOLDOWN)
                log("Cooldown over - resuming.")
                continue
            raise
