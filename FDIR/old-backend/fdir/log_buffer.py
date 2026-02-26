from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional

from .types import LogEntry


class LogBuffer:
    def __init__(self, capacity: int = 2000):
        self._seq = 0
        self._buf: Deque[LogEntry] = deque(maxlen=capacity)

    @property
    def seq(self) -> int:
        return self._seq

    def add(self, level: str, stage: str, message: str, details: Optional[Dict] = None) -> LogEntry:
        self._seq += 1
        entry = LogEntry(
            seq=self._seq,
            timestamp_iso=datetime.now(timezone.utc).isoformat(),
            level=level,
            stage=stage,
            message=message,
            details=details or {},
        )
        self._buf.append(entry)
        return entry

    def tail(self, limit: int = 200) -> List[LogEntry]:
        if limit <= 0:
            return []
        return list(self._buf)[-limit:]

    def since(self, seq: int) -> List[LogEntry]:
        if seq <= 0:
            return list(self._buf)
        return [e for e in self._buf if e.seq > seq]
