"""Backoff/retry helper (D25/D26) — offline, injected sleep so it runs instantly."""

import pytest

from agentic_memory import (
    call_with_backoff,
    is_overload_error,
    is_quota_error,
    is_retryable,
)


class _Boom(Exception):
    pass


def _err(msg: str) -> Exception:
    return _Boom(msg)


def test_overload_classification():
    assert is_overload_error(_err("Error code: 503"))
    assert is_overload_error(_err("UNAVAILABLE: backend"))
    assert is_overload_error(_err("anthropic overloaded_error"))
    assert not is_overload_error(_err("429 quota"))


def test_quota_classification():
    assert is_quota_error(_err("Error code: 429 - Quota exceeded"))
    assert is_quota_error(_err("RESOURCE_EXHAUSTED"))
    assert is_quota_error(_err("daily quota reached"))
    assert not is_quota_error(_err("503 UNAVAILABLE"))


def test_retryable_is_union_and_excludes_other_errors():
    assert is_retryable(_err("503"))
    assert is_retryable(_err("429"))
    assert not is_retryable(_err("ValidationError: bad schema"))


def test_returns_immediately_on_success():
    calls = {"n": 0}
    slept: list[float] = []

    def fn():
        calls["n"] += 1
        return "ok"

    assert call_with_backoff(fn, sleep=slept.append) == "ok"
    assert calls["n"] == 1 and slept == []  # no retry, no sleep


def test_retries_then_succeeds_with_exponential_backoff():
    attempts = {"n": 0}
    slept: list[float] = []

    def fn():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise _err("Error code: 429 - throttled")
        return "recovered"

    out = call_with_backoff(fn, attempts=4, base_delay=6.0, sleep=slept.append)
    assert out == "recovered"
    assert attempts["n"] == 3
    assert slept == [6.0, 12.0]  # 6 → 12, exponential; no sleep after the success


def test_persistent_quota_exhausts_and_reraises_last():
    notices: list[int] = []
    slept: list[float] = []

    def fn():
        raise _err("429 RESOURCE_EXHAUSTED")

    with pytest.raises(_Boom, match="RESOURCE_EXHAUSTED"):
        call_with_backoff(
            fn, attempts=3, base_delay=6.0, sleep=slept.append,
            on_retry=lambda n, d, e: notices.append(n),
        )
    assert notices == [1, 2]          # notified before each of the 2 backoffs
    assert slept == [6.0, 12.0]       # slept twice, not after the final failure


def test_non_retryable_raises_immediately_without_sleeping():
    calls = {"n": 0}
    slept: list[float] = []

    def fn():
        calls["n"] += 1
        raise ValueError("not a transient error")

    with pytest.raises(ValueError):
        call_with_backoff(fn, sleep=slept.append)
    assert calls["n"] == 1 and slept == []  # one try, no backoff
