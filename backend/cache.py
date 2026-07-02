"""
In-memory cache for /query results, keyed by normalized question text.

Invalidated automatically whenever worldcup.db or worldcup_stats.db changes
(compared by mtime), so a sync never serves stale answers — no manual TTL.
"""

import hashlib
from collections import OrderedDict
from pathlib import Path

_MAX_ENTRIES = 500
_cache: "OrderedDict[str, dict]" = OrderedDict()

_DB_PATHS = [
    Path(__file__).resolve().parent / "worldcup.db",
    Path(__file__).resolve().parent / "worldcup_stats.db",
]


def _db_fingerprint() -> float:
    return max((p.stat().st_mtime for p in _DB_PATHS if p.exists()), default=0)


def _key(question: str, mode: str | None) -> str:
    normalized = " ".join(question.strip().lower().split())
    return hashlib.sha256(f"{mode or ''}\n{normalized}".encode()).hexdigest()


def get(question: str, mode: str | None = None) -> dict | None:
    key = _key(question, mode)
    entry = _cache.get(key)
    if not entry or entry["db_fingerprint"] != _db_fingerprint():
        return None
    _cache.move_to_end(key)
    return entry["result"]


def set(question: str, result: dict, mode: str | None = None) -> None:
    key = _key(question, mode)
    _cache[key] = {"db_fingerprint": _db_fingerprint(), "result": result}
    _cache.move_to_end(key)
    while len(_cache) > _MAX_ENTRIES:
        _cache.popitem(last=False)
