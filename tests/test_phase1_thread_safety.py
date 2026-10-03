"""Thread-safety test for sentinel_utils._consecutive_api_failures (2026-09-27):
the ablations drive openrouter_chat from a ThreadPoolExecutor, so the shared
five-consecutive-failures breaker's counter must be exact under concurrent
increments/resets, not merely "still trips eventually".

No network: every call is answered locally by a fake requests.post (patched
exactly once, outside the worker threads -- unittest.mock.patch is itself not
safe to enter/exit concurrently from many threads); no HTTP leaves the
process.
"""
import threading
from unittest import mock

import pytest

import arch_patch_harness as H
from llm_mcda.common import sentinel_utils as SU
from llm_mcda.common.model_config import (MAX_RETRIES, REQUEST_TIMEOUT, RETRY_BASE_DELAY, MAX_RETRY_BACKOFF,
                          _is_transient_http_status)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    SU._consecutive_api_failures = 0
    yield
    SU._consecutive_api_failures = 0


class ThreadSafePoster(H.Poster):
    """H.Poster with a lock: requests.post is patched ONCE, before any worker
    thread starts, and every thread then calls through this single instance."""

    def __init__(self, script):
        super().__init__(script)
        self._lock = threading.Lock()

    def __call__(self, url, headers=None, json=None, timeout=None):
        with self._lock:
            return super().__call__(url, headers=headers, json=json, timeout=timeout)


DUMMY_PAYLOAD = {"model": "x", "messages": [], "temperature": 0.3, "max_tokens": 8192,
                "provider": {}}
DUMMY_HEADERS = {"Authorization": "Bearer x"}


def _run_chat():
    """Assumes requests.post is already patched (by the caller, once, before
    any thread starts)."""
    return SU.openrouter_chat(
        DUMMY_PAYLOAD, DUMMY_HEADERS,
        endpoint="https://openrouter.ai/api/v1/chat/completions",
        max_retries=MAX_RETRIES, timeout=REQUEST_TIMEOUT, is_transient=_is_transient_http_status,
        base_delay=RETRY_BASE_DELAY, max_backoff=MAX_RETRY_BACKOFF, logger=None,
    )


def bad_request():
    """A 400: fails after BAD_REQUEST_MAX_ATTEMPTS (2) POSTs, without ever
    reaching the breaker's threshold from a single call on its own."""
    return H.FakeResponse(400, {"error": {"code": 400, "message": "bad parameter"}})


def _run_threads(n, target):
    barrier = threading.Barrier(n)

    def worker():
        barrier.wait()
        target()

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
        assert not t.is_alive(), "a worker thread hung"


def test_exact_count_under_concurrent_failures_below_threshold():
    """MAX_CONSECUTIVE_API_FAILURES - 1 threads each fail once, concurrently.
    None should trip the breaker (all stay below threshold), and the shared
    counter must land at exactly n_threads: a lost read-modify-write update
    (the pre-lock `+= 1` is not atomic across bytecode boundaries) would
    undercount it instead."""
    n_threads = SU.MAX_CONSECUTIVE_API_FAILURES - 1  # 4
    assert n_threads > 1
    results = []
    lock = threading.Lock()

    def worker():
        try:
            out = _run_chat()
            with lock:
                results.append(("ok_call", out))
        except SU.OpenRouterFatalError as exc:
            with lock:
                results.append(("abort", exc))

    poster = ThreadSafePoster([bad_request()])
    with mock.patch("requests.post", poster):
        _run_threads(n_threads, worker)

    assert len(results) == n_threads
    aborts = [r for kind, r in results if kind == "abort"]
    assert len(aborts) == 0, "no thread should reach the threshold on its own"
    assert SU._consecutive_api_failures == n_threads


def test_exact_trip_at_threshold_under_many_concurrent_workers():
    """N > MAX_CONSECUTIVE_API_FAILURES threads all fail concurrently. A
    correctly-locked counter serialises every increment into a gap-free,
    duplicate-free sequence 1..N assigned across the threads (each thread's
    own post-increment value is unique), so:
      - exactly N - (threshold - 1) threads see a count >= threshold and abort
        (the ones assigned counts threshold..N);
      - the abort messages' embedded counts are exactly that set, with no
        duplicate and no value below threshold;
      - the counter lands at exactly N.
    A lost update (the unlocked `+= 1`) would instead let some counts repeat
    or be skipped, changing both the abort count and which values appear.
    """
    import re

    n_threads = 24
    results = []
    lock = threading.Lock()

    def worker():
        try:
            out = _run_chat()
            with lock:
                results.append(("ok_call", out))
        except SU.OpenRouterFatalError as exc:
            with lock:
                results.append(("abort", exc))

    poster = ThreadSafePoster([bad_request()])
    with mock.patch("requests.post", poster):
        _run_threads(n_threads, worker)

    assert len(results) == n_threads
    aborts = [r for kind, r in results if kind == "abort"]
    threshold = SU.MAX_CONSECUTIVE_API_FAILURES
    assert len(aborts) == n_threads - (threshold - 1)

    counts = sorted(int(re.match(r"ABORT: (\d+) consecutive", str(exc)).group(1)) for exc in aborts)
    assert counts == list(range(threshold, n_threads + 1))  # gap-free, duplicate-free, all >= threshold

    # Monotonic non-decreasing across 24 concurrent increments (no success
    # resets it here), so it must land at exactly n_threads: a lost update
    # would leave it strictly below.
    assert SU._consecutive_api_failures == n_threads


def test_success_resets_are_also_serialised():
    """A run of serial failures, then one success, resets the counter exactly;
    then many concurrent successes must all land the counter at exactly 0."""
    poster = ThreadSafePoster([bad_request()])
    with mock.patch("requests.post", poster):
        for _ in range(3):
            _run_chat()
    assert SU._consecutive_api_failures == 3

    ok_poster = ThreadSafePoster([H.ok(H.SCORES_JSON)])
    with mock.patch("requests.post", ok_poster):
        _run_chat()
    assert SU._consecutive_api_failures == 0

    # Hammer resets from many threads: every call succeeds, so the counter
    # must land at exactly 0 regardless of interleaving.
    n_threads = 16
    with mock.patch("requests.post", ThreadSafePoster([H.ok(H.SCORES_JSON)])):
        _run_threads(n_threads, _run_chat)
    assert SU._consecutive_api_failures == 0


def test_hammer_increments_and_resets_directly_for_an_exact_final_count():
    """Bypasses openrouter_chat's network path entirely and hammers the
    counter's own increment/reset primitives from many threads, so the
    assertion is purely about _consecutive_api_failures_lock's correctness:
    n_threads threads each do exactly one increment (mirroring
    _count_failure_and_maybe_abort's critical section, with the threshold
    raised out of the way so every increment lands), and the final count must
    equal n_threads exactly -- a lost update under the bare `+= 1` would leave
    it lower."""
    n_threads = 200
    barrier = threading.Barrier(n_threads)

    def increment_once():
        barrier.wait()
        with SU._consecutive_api_failures_lock:
            SU._consecutive_api_failures += 1

    threads = [threading.Thread(target=increment_once) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
        assert not t.is_alive()
    assert SU._consecutive_api_failures == n_threads
