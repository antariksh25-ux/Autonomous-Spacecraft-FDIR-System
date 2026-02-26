from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from ..config import channel_index
from ..types import ChannelSpec


class AnomalyDetection:
    """Rule-based anomaly detection with persistence + cross-sensor validation."""

    def __init__(self, channels: List[ChannelSpec], persistence_samples: int, cross_sensor_min: int):
        self._idx = channel_index(channels)
        self._persistence = max(1, int(persistence_samples))
        self._cross_min = max(1, int(cross_sensor_min))
        self._consecutive_oob: Dict[str, int] = defaultdict(int)

    def update(self, telemetry: Dict[str, float]) -> Dict[str, List[str]]:
        confirmed: Dict[str, List[str]] = defaultdict(list)

        for name, spec in self._idx.items():
            if name not in telemetry:
                continue
            v = float(telemetry[name])
            oob = not (spec.nominal_min <= v <= spec.nominal_max)
            if oob:
                self._consecutive_oob[name] += 1
            else:
                self._consecutive_oob[name] = 0

        for name, count in self._consecutive_oob.items():
            if count >= self._persistence:
                spec = self._idx.get(name)
                if spec:
                    confirmed[spec.subsystem].append(name)

        out: Dict[str, List[str]] = {}
        for subsystem, chans in confirmed.items():
            if len(chans) >= self._cross_min:
                out[subsystem] = sorted(chans)
        return out
