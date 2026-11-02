"""
Gateway event log, counters, kill switch and rate limiter.

Every decision the gateway makes (tool allowed / denied / masked / flagged,
model call routed / blocked) is appended here. The Governance console polls
it to show decisions live. In-memory; cleared by "Reset demo".
"""
import time
from collections import deque, defaultdict

MAX_EVENTS = 3000

_events: deque = deque(maxlen=MAX_EVENTS)
_next_id = 1
_kill_switch = {"enabled": False, "by": None, "at": None}
_rate: dict[str, deque] = defaultdict(deque)

_counters = defaultdict(int)
_lanes = {
    "private": {"calls": 0, "bytes_out": 0, "bytes_in": 0, "blocked": 0},
    "public": {"calls": 0, "bytes_out": 0, "bytes_in": 0, "blocked": 0},
}


def record(kind: str, decision: str, *, employee: dict | None = None, client_id: str | None = None,
           tool: str | None = None, lane: str | None = None, detail: str = "", request_id: str | None = None,
           extra: dict | None = None) -> dict:
    global _next_id
    ev = {
        "id": _next_id,
        "ts": time.time(),
        "kind": kind,              # tool | model | lane | admin | bypass
        "decision": decision,      # allowed | denied | masked | flagged | routed | blocked | info
        "employee": employee["username"] if employee else None,
        "role": employee["role"] if employee else None,
        "client_id": client_id,
        "tool": tool,
        "lane": lane,
        "detail": detail,
        "request_id": request_id,
        **(extra or {}),
    }
    _next_id += 1
    _events.append(ev)
    _counters[decision] += 1
    return ev


def events_since(since_id: int = 0, limit: int = 300) -> list[dict]:
    out = [e for e in _events if e["id"] > since_id]
    return out[-limit:]


def lane_add(lane: str, bytes_out: int = 0, bytes_in: int = 0, blocked: bool = False):
    s = _lanes[lane]
    if blocked:
        s["blocked"] += 1
    else:
        s["calls"] += 1
        s["bytes_out"] += bytes_out
        s["bytes_in"] += bytes_in


def stats() -> dict:
    return {
        "counters": dict(_counters),
        "lanes": {k: dict(v) for k, v in _lanes.items()},
        "kill_switch": dict(_kill_switch),
        "last_event_id": _next_id - 1,
    }


def kill_switch_enabled() -> bool:
    return _kill_switch["enabled"]


def set_kill_switch(enabled: bool, by: str):
    _kill_switch.update({"enabled": enabled, "by": by, "at": time.time()})


def rate_limited(username: str, per_min: int) -> bool:
    q = _rate[username]
    now = time.time()
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= per_min:
        return True
    q.append(now)
    return False


def reset():
    global _next_id
    _events.clear()
    _next_id = 1
    _counters.clear()
    _rate.clear()
    for s in _lanes.values():
        for k in s:
            s[k] = 0
    _kill_switch.update({"enabled": False, "by": None, "at": None})
