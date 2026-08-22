"""In-memory, per-process sliding-window rate limiter.

Deliberately simple: this runs as a single backend instance (Render free tier,
one dyno), so there's no need for a shared store like Redis — an in-memory dict
keyed by uid is enough. The documented tradeoff is that limits reset on restart
or redeploy, and wouldn't be shared across multiple instances if this ever scaled
horizontally; a real production version would move this to Redis at that point.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, status

_WINDOW_SECONDS = 60.0
_MAX_REQUESTS_PER_WINDOW = 5

_hits: dict[str, deque[float]] = defaultdict(deque)


def enforce_note_submission_rate_limit(uid: str) -> None:
    """Raises 429 if this uid has submitted more than _MAX_REQUESTS_PER_WINDOW
    notes in the last _WINDOW_SECONDS. Applied to note submission specifically —
    that's the route that costs a real Gemini call, unlike reads."""
    now = time.monotonic()
    window = _hits[uid]
    while window and now - window[0] > _WINDOW_SECONDS:
        window.popleft()
    if len(window) >= _MAX_REQUESTS_PER_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many notes submitted in a short time — please wait a moment and try again.",
        )
    window.append(now)


def _reset_for_tests() -> None:
    _hits.clear()
