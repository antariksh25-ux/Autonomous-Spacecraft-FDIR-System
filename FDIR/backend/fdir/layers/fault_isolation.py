from __future__ import annotations

from typing import Dict, List, Tuple

from ..config import channel_index
from ..types import ChannelSpec, IsolationResult, Severity


class FaultIsolation:
    def __init__(self, channels: List[ChannelSpec]):
        self._idx = channel_index(channels)

    def isolate(self, telemetry: Dict[str, float], confirmed_by_subsystem: Dict[str, List[str]]) -> List[IsolationResult]:
        results: List[IsolationResult] = []
        for subsystem, chans in confirmed_by_subsystem.items():
            component, fault_type = self._classify(subsystem, chans)
            confidence, severity, rationale = self._score(chans, telemetry)
            results.append(
                IsolationResult(
                    subsystem=subsystem,
                    component=component,
                    fault_type=fault_type,
                    severity=severity,
                    confidence=confidence,
                    rationale=rationale,
                )
            )
        return results

    def _classify(self, subsystem: str, chans: List[str]) -> Tuple[str, str]:
        s = subsystem.lower()
        if s == "power":
            if any("voltage" in c for c in chans) and any("current" in c for c in chans):
                return "power_regulator", "power_regulation_anomaly"
            if any("voltage" in c for c in chans):
                return "bus_voltage_sensor", "voltage_out_of_range"
            return "load_monitor", "current_out_of_range"
        if s == "thermal":
            if len(chans) >= 3:
                return "thermal_control", "thermal_runaway"
            return "temp_sensor", "temperature_out_of_range"
        if s == "communication":
            if "packet_loss" in chans:
                return "link_layer", "packet_loss_high"
            if "signal_strength" in chans:
                return "rf_frontend", "signal_strength_low"
            return "network_stack", "latency_high"
        if s == "attitude":
            if any(c.startswith("gyro_") for c in chans):
                return "gyro", "rate_out_of_range"
            return "imu", "acc_out_of_range"
        return "unknown", "anomaly"

    def _score(self, chans: List[str], telemetry: Dict[str, float]) -> Tuple[float, Severity, str]:
        devs: List[float] = []
        for c in chans:
            spec = self._idx.get(c)
            if not spec or c not in telemetry:
                continue
            v = float(telemetry[c])
            if v < spec.nominal_min:
                denom = max(1e-9, abs(spec.nominal_min))
                devs.append((spec.nominal_min - v) / denom)
            elif v > spec.nominal_max:
                denom = max(1e-9, abs(spec.nominal_max))
                devs.append((v - spec.nominal_max) / denom)

        dev_score = min(1.0, max(devs, default=0.0) / 0.5)
        chan_score = min(1.0, len(chans) / 4.0)
        confidence = max(0.05, min(1.0, 0.35 * chan_score + 0.65 * dev_score))

        severity = Severity.yellow
        if confidence >= 0.8:
            severity = Severity.red
        elif confidence < 0.4:
            severity = Severity.green

        rationale = f"Confirmed channels={len(chans)}; max_norm_deviation={max(devs, default=0.0):.2f}"
        return confidence, severity, rationale
