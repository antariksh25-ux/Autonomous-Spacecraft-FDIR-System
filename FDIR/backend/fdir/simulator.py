from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

import math
import random


@dataclass
class InjectedFault:
    name: str
    magnitude: float
    until_t: float


class SpacecraftSimulator:
    """Deterministic, lightweight spacecraft telemetry simulator.

    "Physics-ish" here means we model subsystems with simple first-order dynamics and coupling:
    - Power load affects thermal.
    - Attitude disturbance affects comm link margin.
    - Fault injections perturb these dynamics.

    This is designed to be stable and reproducible (seeded RNG).
    """

    def __init__(self, seed: int = 7):
        self._rng = random.Random(int(seed))
        self.t = 0.0
        self._fault: Optional[InjectedFault] = None

        # Internal state variables (continuous)
        self._bus_v = 28.0
        self._bus_i = 4.0
        self._temp = 22.0
        self._gyro = 0.0
        self._acc = 0.0

        self._snr_db = -70.0
        self._packet_loss = 0.3
        self._latency = 120.0

        # Slowly varying exogenous inputs
        self._sun_factor = 0.5
        self._load_factor = 0.4

    def inject_fault(self, name: str, magnitude: float, duration_s: float) -> None:
        name = str(name).lower()
        duration_s = max(0.1, float(duration_s))
        self._fault = InjectedFault(name=name, magnitude=float(magnitude), until_t=self.t + duration_s)

    def clear_fault(self) -> None:
        self._fault = None

    def fault_status(self) -> Optional[Dict[str, float | str]]:
        f = self._active_fault()
        if not f:
            return None
        return {
            "name": f.name,
            "magnitude": float(f.magnitude),
            "remaining_s": float(max(0.0, f.until_t - self.t)),
        }

    def _active_fault(self) -> Optional[InjectedFault]:
        if not self._fault:
            return None
        if self.t <= self._fault.until_t:
            return self._fault
        self._fault = None
        return None

    def step(self, dt: float) -> Dict[str, float]:
        dt = max(1e-3, float(dt))
        self.t += dt
        f = self._active_fault()

        # Exogenous environment/load variations (bounded)
        self._sun_factor = 0.5 + 0.45 * math.sin(2.0 * math.pi * self.t / 180.0)
        self._load_factor = 0.4 + 0.25 * math.sin(2.0 * math.pi * self.t / 75.0)

        # Baseline dynamics
        target_v = 28.0
        target_i = 3.0 + 6.0 * max(0.0, self._load_factor)
        target_temp = 18.0 + 35.0 * max(0.0, self._sun_factor) + 2.0 * (self._bus_i / 10.0)

        # Fault effects
        if f:
            if f.name == "power_regulator_failure":
                target_v -= 6.0 * min(1.5, abs(f.magnitude))
                target_i += 2.0 * min(2.0, abs(f.magnitude))
            elif f.name == "thermal_runaway":
                target_temp += 25.0 * min(2.0, abs(f.magnitude))
            elif f.name == "communication_dropout":
                self._snr_db -= 35.0 * min(2.0, abs(f.magnitude))
                self._packet_loss += 12.0 * min(2.0, abs(f.magnitude))
                self._latency += 600.0 * min(2.0, abs(f.magnitude))
            elif f.name == "attitude_drift":
                self._gyro += 0.6 * min(2.0, abs(f.magnitude))

        # First-order response (stable)
        self._bus_v += (target_v - self._bus_v) * (1.0 - math.exp(-dt / 4.0))
        self._bus_i += (target_i - self._bus_i) * (1.0 - math.exp(-dt / 6.0))
        self._temp += (target_temp - self._temp) * (1.0 - math.exp(-dt / 20.0))

        # Attitude dynamics
        self._gyro += (-0.15 * self._gyro) * dt
        self._acc += (-0.2 * self._acc) * dt

        # Coupling: attitude affects comm margin
        pointing_penalty = min(8.0, abs(self._gyro) * 6.0)
        self._snr_db += (-0.3 * (self._snr_db + 70.0) - pointing_penalty * 0.03) * dt
        self._packet_loss += (-0.35 * (self._packet_loss - 0.3) + max(0.0, pointing_penalty - 1.0) * 0.03) * dt
        self._latency += (-0.25 * (self._latency - 120.0) + self._packet_loss * 0.8) * dt

        # Add small deterministic noise
        def n(scale: float) -> float:
            return self._rng.uniform(-scale, scale)

        telemetry = {
            "voltage_1": self._bus_v + n(0.08),
            "voltage_2": self._bus_v + n(0.08),
            "current_1": self._bus_i + n(0.05),
            "current_2": self._bus_i + n(0.05),
            "temp_1": self._temp + n(0.12),
            "temp_2": self._temp + n(0.12),
            "temp_3": self._temp + n(0.12),
            "temp_4": self._temp + n(0.12),
            "gyro_x": self._gyro + n(0.01),
            "gyro_y": (-self._gyro * 0.4) + n(0.01),
            "gyro_z": (self._gyro * 0.2) + n(0.01),
            "acc_x": self._acc + n(0.02),
            "acc_y": (-self._acc * 0.5) + n(0.02),
            "acc_z": (self._acc * 0.2) + n(0.02),
            "signal_strength": self._snr_db + n(0.5),
            "packet_loss": max(0.0, self._packet_loss + n(0.08)),
            "latency": max(0.0, self._latency + n(3.0)),
        }

        # Clamp a few values to avoid numeric runaway
        telemetry["packet_loss"] = float(min(100.0, telemetry["packet_loss"]))

        return telemetry

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
