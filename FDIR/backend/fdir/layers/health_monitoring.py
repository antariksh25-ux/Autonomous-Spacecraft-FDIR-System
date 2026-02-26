from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from ..config import channel_index
from ..types import ChannelSpec, SensorHealth, Severity, SubsystemHealth


def _deviation(value: float, lo: float, hi: float) -> float:
    if lo <= value <= hi:
        return 0.0
    if value < lo:
        denom = max(1e-9, abs(lo))
        return min(10.0, (lo - value) / denom)
    denom = max(1e-9, abs(hi))
    return min(10.0, (value - hi) / denom)


class HealthMonitoring:
    def __init__(self, channels: List[ChannelSpec]):
        self._idx = channel_index(channels)

    def evaluate(self, telemetry: Dict[str, float]) -> List[SubsystemHealth]:
        per_sub: Dict[str, List[SensorHealth]] = defaultdict(list)
        for name, spec in self._idx.items():
            if name not in telemetry:
                continue
            v = float(telemetry[name])
            within = spec.nominal_min <= v <= spec.nominal_max
            dev = _deviation(v, spec.nominal_min, spec.nominal_max)
            per_sub[spec.subsystem].append(
                SensorHealth(
                    channel=name,
                    value=v,
                    nominal_min=spec.nominal_min,
                    nominal_max=spec.nominal_max,
                    within_nominal=within,
                    deviation=dev,
                )
            )

        out: List[SubsystemHealth] = []
        for subsystem, sensors in per_sub.items():
            abnormal = [s for s in sensors if not s.within_nominal]
            if not abnormal:
                severity = Severity.green
                summary = "All sensors within nominal range"
            else:
                max_dev = max((s.deviation for s in abnormal), default=0.0)
                severity = Severity.yellow if max_dev < 0.25 else Severity.red
                summary = f"{len(abnormal)}/{len(sensors)} sensors out of nominal"

            out.append(SubsystemHealth(subsystem=subsystem, severity=severity, summary=summary, sensors=sensors))

        return sorted(out, key=lambda h: h.subsystem)
