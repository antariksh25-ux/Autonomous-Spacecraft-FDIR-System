from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .types import ChannelSpec, TelemetrySample


@dataclass
class TelemetryState:
    last_sample: Optional[TelemetrySample] = None
    last_rx_iso: Optional[str] = None
    total_samples: int = 0


class TelemetryStore:
    """In-memory telemetry store.

    Keeps latest value per channel and a short history for charting.
    """

    def __init__(self, channels: List[ChannelSpec], history_len: int = 600):
        self._channels = {c.name: c for c in channels}
        self._history_len = history_len
        self._history: Dict[str, List[Tuple[float, float]]] = {name: [] for name in self._channels}
        self.state = TelemetryState()
        self._t0 = datetime.utcnow().timestamp()

    def ingest(self, sample: TelemetrySample) -> None:
        now_ts = datetime.utcnow().timestamp()
        t = now_ts - self._t0

        filtered: Dict[str, float] = {
            k: float(v) for k, v in sample.values.items() if k in self._channels and v is not None
        }
        self.state.last_sample = TelemetrySample(timestamp_iso=sample.timestamp_iso, values=filtered)
        self.state.last_rx_iso = sample.timestamp_iso
        self.state.total_samples += 1

        for name, value in filtered.items():
            arr = self._history.get(name)
            if arr is None:
                continue
            arr.append((t, value))
            if len(arr) > self._history_len:
                del arr[: max(0, len(arr) - self._history_len)]

    def latest_values(self) -> Dict[str, float]:
        return dict(self.state.last_sample.values) if self.state.last_sample else {}
