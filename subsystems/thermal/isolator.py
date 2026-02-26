"""
subsystems/thermal/isolator.py
===============================
Fault signature library for the Thermal Subsystem.

Fault types:
  thermal_runaway       — component bay overheating, risk of hardware damage
  heater_failure        — primary heater output loss, spacecraft cooling
  radiator_degradation  — radiator can't reject heat, internal temp rising
"""

THERMAL_FAULT_SIGNATURES = {
    "thermal_runaway": {
        "primary_param":   "internal_temp",
        "corroborating":   ["radiator_temp"],
        "contradicting":   [],
        "risk_level":      "HIGH",
        "reversibility":   "MEDIUM",
        "description":     "Component bay thermal runaway — temperature rising uncontrollably, risk of hardware damage",
        "recovery_action": "thermal_throttle",
        "base_confidence": 0.70,
    },
    "heater_failure": {
        "primary_param":   "heater_power",
        "corroborating":   ["panel_temp"],
        "contradicting":   [],
        "risk_level":      "MEDIUM",
        "reversibility":   "HIGH",
        "description":     "Primary heater output failure — spacecraft cooling below safe operating limits",
        "recovery_action": "switch_to_backup_heater",
        "base_confidence": 0.75,
    },
    "radiator_degradation": {
        "primary_param":   "radiator_temp",
        "corroborating":   ["internal_temp"],
        "contradicting":   [],
        "risk_level":      "MEDIUM",
        "reversibility":   "HIGH",
        "description":     "Radiator thermal performance degradation — heat rejection capacity reduced",
        "recovery_action": "activate_emergency_radiator",
        "base_confidence": 0.68,
    },
}
