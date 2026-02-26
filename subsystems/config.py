"""
config.py
=========
Central configuration for the FDIR System — 5-Fault Demo Scenario.

SCENARIO OVERVIEW:
  Fault 1 — Power:   voltage_drop     T010  → FULL_AUTONOMOUS   (machine solves completely)
  Fault 2 — Thermal: heater_failure   T025  → FULL_AUTONOMOUS   (machine solves completely)
  Fault 3 — Power:   overcurrent      T045  → LIMITED_ACTION    (half solved — reduce_load applied,
                                                                   full fix escalated to ground)
  Fault 4 — Power:   battery_drain    T065  → HUMAN_ESCALATION  (HIGH risk, ground station must decide)
  Fault 5 — Thermal: thermal_runaway  T080  → HUMAN_ESCALATION  (HIGH risk, ground station must decide)
"""

# ─────────────────────────────────────────────
# SHARED SETTINGS
# ─────────────────────────────────────────────
NOISE_BAND         = 3.0
PERSISTENCE_WINDOW = 3

ETHICAL = {
    "confidence_high":   0.75,
    "confidence_medium": 0.45,
}

MISSION_PHASE = "NOMINAL_OPS"

MISSION_PHASE_CRITICALITY = {
    "NOMINAL_OPS":       "LOW",
    "COMMS_BLACKOUT":    "MEDIUM",
    "CRITICAL_MANEUVER": "HIGH",
    "SAFE_MODE":         "HIGH",
}


# ═════════════════════════════════════════════
# POWER SUBSYSTEM
# ═════════════════════════════════════════════
POWER_NOMINAL = {
    "voltage":     {"min": 45, "max": 75, "nominal": 60},
    "current":     {"min": 20, "max": 60, "nominal": 35},
    "soc":         {"min": 30, "max": 100, "nominal": 80},
    "temperature": {"min": 10, "max": 70,  "nominal": 35},
}

POWER_THRESHOLDS = {
    "voltage":     {"warning": 50, "critical": 38},
    "current":     {"warning": 65, "critical": 78},
    "soc":         {"warning": 35, "critical": 22},
    "temperature": {"warning": 72, "critical": 85},
}

POWER_FAULT_DIRECTION = {
    "voltage":     "lower",
    "current":     "upper",
    "soc":         "lower",
    "temperature": "upper",
}

POWER_NOISE_AMPLITUDE = 2.0

POWER_FAULT_INJECTION_TIMELINE = [
    {
        # FAULT 1 — Fully autonomous resolution
        # voltage_drop: 78% conf + LOW risk → FULL_AUTONOMOUS → switch_to_backup_regulator
        "tick":         10,
        "type":         "voltage_drop",
        "severity":     "gradual",
        "description":  "[FAULT 1/5] Primary regulator partial failure — voltage declining",
        "target_value": 30,
    },
    {
        # FAULT 3 — Half solved (LIMITED_ACTION)
        # overcurrent: 65% conf → medium range → LIMITED_ACTION → reduce_load applied
        # Ground station alerted to authorize full load isolation
        "tick":         45,
        "type":         "overcurrent",
        "severity":     "gradual",
        "description":  "[FAULT 3/5] Excess current draw on primary bus — possible short circuit",
        "target_value": 82,
    },
    {
        # FAULT 4 — Forwarded to ground station
        # battery_drain: HIGH risk → HUMAN_ESCALATION regardless of confidence
        "tick":         50,   # injected at T050 — detects ~T073
        "type":         "battery_drain",
        "severity":     "gradual",
        "description":  "[FAULT 4/5] Abnormal battery depletion — charge controller suspected",
        "target_value": 15,
    },
]


# ═════════════════════════════════════════════
# THERMAL SUBSYSTEM
# ═════════════════════════════════════════════
THERMAL_NOMINAL = {
    "internal_temp": {"min": 15, "max": 65, "nominal": 40},
    "radiator_temp": {"min":  5, "max": 55, "nominal": 22},
    "heater_power":  {"min": 10, "max": 90, "nominal": 50},
    "panel_temp":    {"min":  5, "max": 55, "nominal": 28},
}

THERMAL_THRESHOLDS = {
    "internal_temp": {"warning": 58, "critical": 72},
    "radiator_temp": {"warning": 45, "critical": 58},
    "heater_power":  {"warning": 22, "critical": 12},
    "panel_temp":    {"warning": 12, "critical":  6},
}

THERMAL_FAULT_DIRECTION = {
    "internal_temp": "upper",
    "radiator_temp": "upper",
    "heater_power":  "lower",
    "panel_temp":    "lower",
}

THERMAL_NOISE_AMPLITUDE = 1.5

THERMAL_FAULT_INJECTION_TIMELINE = [
    {
        # FAULT 2 — Fully autonomous resolution
        # heater_failure: raised to 78% conf + MEDIUM risk + HIGH reversibility
        # → FULL_AUTONOMOUS → switch_to_backup_heater
        "tick":         25,
        "type":         "heater_failure",
        "severity":     "gradual",
        "description":  "[FAULT 2/5] Primary heater output degrading — thermal control at risk",
        "target_value": 8,
    },
    {
        # FAULT 5 — Forwarded to ground station
        # thermal_runaway: HIGH risk + MEDIUM reversibility → HUMAN_ESCALATION
        "tick":         95,   # injected at T095 — well after battery_drain detection
        "type":         "thermal_runaway",
        "severity":     "gradual",
        "description":  "[FAULT 5/5] Component bay overheating — thermal runaway detected",
        "target_value": 85,
    },
]


# ─────────────────────────────────────────────
# BACKWARD COMPATIBILITY ALIASES
# ─────────────────────────────────────────────
NOMINAL                  = POWER_NOMINAL
ANOMALY_THRESHOLDS       = POWER_THRESHOLDS
NOISE_AMPLITUDE          = POWER_NOISE_AMPLITUDE
FAULT_INJECTION_TIMELINE = POWER_FAULT_INJECTION_TIMELINE


# ─────────────────────────────────────────────
# SYSTEM SETTINGS
# ─────────────────────────────────────────────
TICK_INTERVAL_SECONDS = 1.0
LOG_FILE  = "fdir_event_log.json"
API_HOST  = "0.0.0.0"
API_PORT  = 8000