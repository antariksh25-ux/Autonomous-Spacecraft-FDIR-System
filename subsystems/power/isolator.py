"""
subsystems/power/isolator.py
=============================
Fault signature library for the Power Subsystem.

Each signature defines:
  - primary_param:   the sensor that must be anomalous
  - corroborating:   sensors that boost confidence when also anomalous
  - contradicting:   sensors that reduce confidence if anomalous
  - base_confidence: starting confidence when primary is confirmed
  - risk_level, reversibility: fed to ethical engine
  - recovery_action: recommended recovery step
"""

POWER_FAULT_SIGNATURES = {
    "voltage_drop": {
        "primary_param":   "voltage",
        "corroborating":   ["soc"],
        "contradicting":   [],
        "risk_level":      "LOW",
        "reversibility":   "HIGH",
        "description":     "Primary power regulator voltage drop — likely regulator degradation or partial failure",
        "recovery_action": "switch_to_backup_regulator",
        "base_confidence": 0.78,
    },
    "overcurrent": {
        "primary_param":   "current",
        "corroborating":   ["temperature"],
        "contradicting":   [],
        "risk_level":      "MEDIUM",
        "reversibility":   "HIGH",
        "description":     "Overcurrent condition — excess load on primary bus or short circuit",
        "recovery_action": "reduce_load",
        "base_confidence": 0.65,
    },
    "battery_drain": {
        "primary_param":   "soc",
        "corroborating":   ["voltage"],
        "contradicting":   [],
        "risk_level":      "HIGH",
        "reversibility":   "MEDIUM",
        "description":     "Abnormal battery depletion — possible charge controller failure or excessive load",
        "recovery_action": "emergency_charge",
        "base_confidence": 0.55,
    },
    "thermal_overload": {
        "primary_param":   "temperature",
        "corroborating":   ["current"],
        "contradicting":   [],
        "risk_level":      "HIGH",
        "reversibility":   "MEDIUM",
        "description":     "Regulator thermal overload — risk of permanent hardware damage if unaddressed",
        "recovery_action": "thermal_throttle",
        "base_confidence": 0.70,
    },
}
