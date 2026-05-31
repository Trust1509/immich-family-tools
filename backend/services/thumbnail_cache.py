"""LRU in-memory thumbnail cache with size ceiling."""
import logging
from collections import OrderedDict

logger = logging.getLogger(__name__)


class ThumbnailCache:
    def __init__(self, max_bytes: int = 50 * 1024 * 1024):
        self._max_bytes = max_bytes
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._size = 0

    def _key(self, account_id: str, person_id: str) -> str:
        return f"{account_id}:{person_id}"

    def get(self, account_id: str, person_id: str) -> bytes | None:
        k = self._key(account_id, person_id)
        if k not in self._cache:
            return None
        self._cache.move_to_end(k)
        return self._cache[k]

    def set(self, account_id: str, person_id: str, data: bytes) -> None:
        k = self._key(account_id, person_id)
        if k in self._cache:
            self._size -= len(self._cache[k])
            del self._cache[k]
        self._cache[k] = data
        self._size += len(data)
        self._cache.move_to_end(k)
        # Evict oldest entries until under ceiling
        while self._size > self._max_bytes and self._cache:
            _, evicted = self._cache.popitem(last=False)
            self._size -= len(evicted)

    @property
    def size_bytes(self) -> int:
        return self._size

    @property
    def entry_count(self) -> int:
        return len(self._cache)
