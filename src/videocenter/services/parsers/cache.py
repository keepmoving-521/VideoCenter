from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock

from videocenter.services.parsers.base import ParseResult


@dataclass(frozen=True, slots=True)
class CacheEntry:
    result: ParseResult
    expires_at: datetime


class ParseResultCache:
    def __init__(
        self,
        *,
        ttl_seconds: float = 1800,
        max_entries: int = 500,
        enabled: bool = True,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("解析缓存有效期必须大于零")
        if max_entries < 1:
            raise ValueError("解析缓存最大条目数必须大于零")
        self.ttl = timedelta(seconds=ttl_seconds)
        self.max_entries = max_entries
        self.enabled = enabled
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> ParseResult | None:
        if not self.enabled:
            return None
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= datetime.now(UTC):
                self._entries.pop(key, None)
                return None
            self._entries.move_to_end(key)
            return entry.result

    def set(self, key: str, result: ParseResult) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._entries[key] = CacheEntry(
                result=result,
                expires_at=datetime.now(UTC) + self.ttl,
            )
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)
