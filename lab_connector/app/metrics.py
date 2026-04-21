from __future__ import annotations

import threading
from collections import Counter
from typing import Any


class ConnectorMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: Counter[str] = Counter()

    def inc(self, key: str, amount: int = 1) -> None:
        with self._lock:
            self._counts[key] += amount

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._counts)
