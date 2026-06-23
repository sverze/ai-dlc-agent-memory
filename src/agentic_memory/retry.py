"""Backoff/retry for transient provider errors (D25/D26).

One home for the "is this worth retrying, and how long do I wait" decision that both
entry points (`scripts/live_demo.py`, `scripts/serve_jira.py`) — and any future webhook —
share. Dependency-free; classification is by substring on the exception text because the
provider SDKs surface these as differently-typed errors (anthropic.RateLimitError,
google API errors, httpx) that all stringify with the tell-tale code.

Two transient classes:
- **overload** (HTTP 503 / UNAVAILABLE / "overloaded") — server-side, always worth a retry.
- **quota** (HTTP 429 / RESOURCE_EXHAUSTED) — a *hard* zero-quota 429 won't clear by retrying
  (request a quota increase), but Vertex Dynamic Shared Quota and per-minute caps throttle
  with 429s that DO clear — so we back off a bounded number of times, then surface clearly.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

RetryNotice = Callable[[int, float, Exception], None]


def is_overload_error(exc: Exception) -> bool:
    s = str(exc)
    return "503" in s or "UNAVAILABLE" in s or "overload" in s.lower()


def is_quota_error(exc: Exception) -> bool:
    s = str(exc)
    return "429" in s or "RESOURCE_EXHAUSTED" in s or "quota" in s.lower()


def is_retryable(exc: Exception) -> bool:
    """Transient enough to be worth a backoff-retry (overload or throttle/quota)."""
    return is_overload_error(exc) or is_quota_error(exc)


def call_with_backoff(
    fn: Callable[[], T],
    *,
    attempts: int = 4,
    base_delay: float = 6.0,
    sleep: Callable[[float], None] = time.sleep,
    on_retry: RetryNotice | None = None,
) -> T:
    """Call ``fn``; on a retryable error, exponentially back off and try again.

    Waits ``base_delay * 2**attempt`` between tries (e.g. 6s → 12s → 24s). Non-retryable
    errors propagate immediately. After ``attempts`` exhausted, re-raises the last error so
    the caller can classify it (e.g. quota → request an increase). ``sleep`` is injectable
    so tests run instantly. Returns ``fn``'s result on success.
    """
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — classified below; non-retryable re-raised
            if not is_retryable(exc):
                raise
            last = exc
            if attempt == attempts - 1:
                break
            delay = base_delay * (2**attempt)
            if on_retry is not None:
                on_retry(attempt + 1, delay, exc)
            sleep(delay)
    assert last is not None  # only reached after a retryable failure
    raise last
