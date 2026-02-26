from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from ..types import RecoveryAction


class RecoveryEngine:
    """Recovery recommendations (no actuator side-effects)."""

    def __init__(self, max_attempts: int = 3):
        self._max_attempts = max(1, int(max_attempts))
        self._attempts: Dict[str, int] = {}

    def propose(self, subsystem: str, fault_type: str) -> RecoveryAction:
        key = f"{subsystem}:{fault_type}"
        n = self._attempts.get(key, 0)
        if n >= self._max_attempts:
            return RecoveryAction(action=None, rationale="Max recovery attempts reached", executed=False)

        if subsystem == "power":
            action = "switch_to_backup_regulator"
            rationale = "Stabilize bus by switching regulation path"
        elif subsystem == "thermal":
            action = "enable_safe_thermal_profile"
            rationale = "Reduce thermal load and increase heat rejection"
        elif subsystem == "communication":
            action = "reduce_downlink_rate_and_reacquire"
            rationale = "Trade throughput for link margin and stability"
        elif subsystem == "attitude":
            action = "attitude_controller_reinit"
            rationale = "Reset control loop and re-bias sensors"
        else:
            action = "enter_safe_mode"
            rationale = "Unknown subsystem anomaly; default safe response"

        self._attempts[key] = n + 1
        return RecoveryAction(action=action, rationale=rationale, executed=False)
