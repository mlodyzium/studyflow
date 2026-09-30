from app.core.i18n import tr
from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException

_events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_lock = Lock()
_counters: dict[str, int] = defaultdict(int)


def check_limit(bucket: str, identity: str, limit: int, window_seconds: int) -> None:
    now = monotonic()
    with _lock:
        events = _events[(bucket, identity)]
        while events and events[0] <= now - window_seconds:
            events.popleft()
        if len(events) >= limit:
            _counters[f"rate_limited_{bucket}"] += 1
            wait = max(1, int(events[0] + window_seconds - now))
            raise HTTPException(status_code=429, detail=tr('Too many attempts. Try again later.'), headers={"Retry-After": str(wait)})
        events.append(now)
        _counters[f"requests_{bucket}"] += 1


def count(name: str) -> None:
    with _lock:
        _counters[name] += 1


def record_request(status: int, duration_ms: float) -> None:
    with _lock:
        _counters["http_requests"] += 1
        _counters["http_duration_ms_total"] += round(duration_ms)
        if status >= 500:
            _counters["http_server_errors"] += 1


def snapshot() -> dict[str, int]:
    with _lock:
        return dict(_counters)
