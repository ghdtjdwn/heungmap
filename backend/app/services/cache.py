from __future__ import annotations

import time
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class CacheStats:
    hits: int
    misses: int
    entries: int


class TtlCache(Generic[T]):
    def __init__(self, *, ttl_seconds: float = 300, max_entries: int = 256) -> None:
        if ttl_seconds <= 0 or max_entries <= 0:
            raise ValueError("ttl_seconds와 max_entries는 양수여야 합니다.")
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._items: OrderedDict[str, tuple[float, T]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> T | None:
        item = self._items.get(key)
        now = time.monotonic()
        if item is None:
            self._misses += 1
            return None
        expires_at, value = item
        if expires_at <= now:
            self._items.pop(key, None)
            self._misses += 1
            return None
        self._items.move_to_end(key)
        self._hits += 1
        return deepcopy(value)

    def set(self, key: str, value: T) -> None:
        self._items[key] = (time.monotonic() + self.ttl_seconds, deepcopy(value))
        self._items.move_to_end(key)
        while len(self._items) > self.max_entries:
            self._items.popitem(last=False)

    def invalidate(self, key: str | None = None) -> None:
        if key is None:
            self._items.clear()
        else:
            self._items.pop(key, None)

    @property
    def stats(self) -> CacheStats:
        return CacheStats(hits=self._hits, misses=self._misses, entries=len(self._items))
