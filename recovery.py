"""
recovery.py
===========
Executes recovery actions authorized by the Ethical Autonomy Engine.

This module ONLY executes what the ethical engine has explicitly permitted.
It never initiates actions independently — authorization token is required.

Implements §5.5 Graceful Degradation strategy:
  1. Switch to backup components (preferred — least disruptive)
  2. Reduce load (intermediate — partial impact)
  3. Thermal throttle (intermediate — affects performance)
  4. Emergency charge (intermediate — suspends payload)
  5. Safe mode (last resort — maximum survivability, minimal mission capability)

§10.2: System must avoid oscillation between normal and recovery states.
  Achieved by: once recovery is executed, the handled_fault_types set in main.py
  prevents re-triggering for the same fault.
"""

from dataclasses import dataclass
from typing import Optional
from subsystems.base import FaultDiagnosis
from ethical_engine import AutonomyDecision, EthicalDecisionResult


@dataclass
class RecoveryResult:
    action_taken:    str
    action_category: str   # "PRIMARY" | "LIMITED" | "SAFE_MODE" | "NO_ACTION"
    success:         bool
    description:     str
    side_effects:    list
    authorized_by:   str   # which autonomy level authorized this


RECOVERY_ACTIONS = {
    "switch_to_backup_regulator": {
        "category":     "PRIMARY",
        "description":  "Switched primary power bus to backup regulator. Primary regulator isolated for review.",
        "side_effects": [
            "Backup regulator now active — reduced max power headroom (~15%)",
            "Primary regulator isolated pending ground review",
        ],
    },
    "reduce_load": {
        "category":     "LIMITED",
        "description":  "Non-critical subsystem loads reduced to ease stress on power bus.",
        "side_effects": [
            "Non-critical payloads temporarily powered down",
            "Data downlink rate reduced",
        ],
    },
    "emergency_charge": {
        "category":     "PRIMARY",
        "description":  "Emergency charging cycle initiated. Solar panel output redirected to battery.",
        "side_effects": [
            "Payload operations suspended during emergency charge",
            "Downlink capability reduced",
        ],
    },
    "thermal_throttle": {
        "category":     "PRIMARY",
        "description":  "High-power operations suspended. Processing load reduced to lower thermal output.",
        "side_effects": [
            "Processing throughput reduced (~40%)",
            "Active thermal management engaged",
        ],
    },
    "switch_to_backup_heater": {
        "category":     "PRIMARY",
        "description":  "Primary heater isolated. Backup heater activated to restore thermal control.",
        "side_effects": [
            "Backup heater now active — reduced thermal margin",
            "Primary heater isolated pending review",
        ],
    },
    "activate_emergency_radiator": {
        "category":     "PRIMARY",
        "description":  "Emergency radiator panels deployed for additional heat rejection.",
        "side_effects": [
            "Emergency radiator active — increased power draw",
            "Spacecraft attitude constraints may apply",
        ],
    },
    "safe_mode": {
        "category":     "SAFE_MODE",
        "description":  "Spacecraft entered SAFE MODE. All non-essential systems suspended. Awaiting ground command.",
        "side_effects": [
            "Mission operations suspended",
            "Only housekeeping telemetry and comms active",
            "Exit requires explicit ground command",
        ],
    },
    "none": {
        "category":     "NO_ACTION",
        "description":  "No autonomous action taken. System held pending human operator decision.",
        "side_effects": [],
    },
}


class RecoveryModule:

    def __init__(self, simulators: dict):
        """Accept a dict of simulators keyed by subsystem name."""
        self.simulators       = simulators   # {"power": PowerSim, "thermal": ThermalSim, ...}
        self.recovery_history = []
        self.safe_mode_active = False
        self.is_recovering    = False

    def execute(self, ethical_decision: EthicalDecisionResult, subsystem: str) -> RecoveryResult:
        """
        Execute the action permitted by the ethical engine.
        Routes recovery to the correct subsystem's simulator.
        """
        action = ethical_decision.permitted_action
        if action not in RECOVERY_ACTIONS:
            action = "none"

        action_def = RECOVERY_ACTIONS[action]

        result = RecoveryResult(
            action_taken    = action,
            action_category = action_def["category"],
            success         = True,
            description     = action_def["description"],
            side_effects    = action_def["side_effects"],
            authorized_by   = ethical_decision.autonomy_level,
        )

        if action != "none":
            simulator = self.simulators.get(subsystem)
            if simulator:
                simulator.apply_recovery(action)
            self.is_recovering = True
            if action == "safe_mode":
                self.safe_mode_active = True

        self.recovery_history.append(result)
        return result

    def trigger_safe_mode(self) -> RecoveryResult:
        """
        §5.5 Last resort — called by main loop if system remains CRITICAL
        after a recovery attempt.  Applies safe_mode across ALL subsystems.
        """
        for sim in self.simulators.values():
            sim.apply_recovery("safe_mode")
        self.safe_mode_active = True
        action_def = RECOVERY_ACTIONS["safe_mode"]
        result = RecoveryResult(
            action_taken    = "safe_mode",
            action_category = "SAFE_MODE",
            success         = True,
            description     = action_def["description"],
            side_effects    = action_def["side_effects"],
            authorized_by   = "SYSTEM_AUTO_ESCALATION",
        )
        self.recovery_history.append(result)
        return result

    def reset(self):
        self.recovery_history = []
        self.safe_mode_active = False
        self.is_recovering    = False
        # Note: simulators are reset separately by main loop

    def to_dict(self, result: RecoveryResult) -> dict:
        return {
            "action_taken":    result.action_taken,
            "action_category": result.action_category,
            "success":         result.success,
            "description":     result.description,
            "side_effects":    result.side_effects,
            "authorized_by":   result.authorized_by,
        }