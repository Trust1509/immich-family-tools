"""MatchCache — lives in app.state; holds the computed match list and its TTL metadata."""
import asyncio
from typing import Optional

from models.match import Match


class MatchCache:
    """Thread-safe async cache for the computed match list.

    The cache stores the last computed result and its monotonic timestamp so
    callers can decide whether to recompute based on a TTL.  A single async
    Lock serialises concurrent refresh attempts so only one coroutine computes
    while others wait and share the result.
    """

    def __init__(self):
        self._matches: Optional[list[Match]] = None
        self._ts: float = 0.0
        self.lock: asyncio.Lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    @property
    def matches(self) -> Optional[list[Match]]:
        return self._matches

    @property
    def ts(self) -> float:
        return self._ts

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def set(self, matches: list[Match], ts: float) -> None:
        self._matches = matches
        self._ts = ts

    def invalidate(self) -> None:
        """Clear the cached result so the next request triggers a recompute."""
        self._matches = None
        self._ts = 0.0
