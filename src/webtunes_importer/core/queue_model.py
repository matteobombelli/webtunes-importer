"""Work queue shared by the Links and Search tabs.

One sequential worker drains this queue (concurrent YouTube downloads were
tried in the exporter this app descends from and reverted after 403/429s).
"""

import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum


class ItemStatus(Enum):
    WAITING = "waiting"
    DOWNLOADING = "downloading"
    UPLOADING = "uploading"
    DONE = "done"
    DUPLICATE = "duplicate"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ImportItem:
    """One YouTube video queued from the Search tab."""

    item_id: str
    title: str
    by: str
    url: str
    duration: float | None = None
    thumbnail_url: str | None = None
    status: ItemStatus = ItemStatus.WAITING
    error: str | None = None


@dataclass
class LinkJob:
    """One Links-tab run: a full Spotify/Apple/YouTube URL to import."""

    url: str
    cancel: threading.Event = field(default_factory=threading.Event)


class ImportQueue:
    """Lock-guarded FIFO. claim() blocks (with timeout) until work is available;
    Search items cancelled while waiting are silently dropped."""

    def __init__(self):
        self._lock = threading.Lock()
        self._items: deque[LinkJob | ImportItem] = deque()
        self._available = threading.Semaphore(0)
        self._cancelled: set[str] = set()

    def put(self, unit: LinkJob | ImportItem) -> None:
        with self._lock:
            self._items.append(unit)
        self._available.release()

    def claim(self, timeout: float = 0.5) -> LinkJob | ImportItem | None:
        if not self._available.acquire(timeout=timeout):
            return None
        with self._lock:
            while self._items:
                unit = self._items.popleft()
                if isinstance(unit, ImportItem) and unit.item_id in self._cancelled:
                    self._cancelled.discard(unit.item_id)
                    unit.status = ItemStatus.CANCELLED
                    continue
                return unit
        return None

    def cancel_item(self, item_id: str) -> None:
        with self._lock:
            self._cancelled.add(item_id)

    def pending_count(self) -> int:
        with self._lock:
            return len(self._items)
