"""
config.py
=========
Central configuration for the FDIR System.
All thresholds use a normalized 0-100 scale for clarity.

Supports multiple subsystems with independent configurations.
Edit *_FAULT_INJECTION_TIMELINE and MISSION_PHASE to control demo scenarios.
"""

# ─────────────────────────────────────────────
# SHARED SETTINGS
# ─────────────────────────────────────────────

# Noise band around WARNING threshold — readings this close to the threshold
# require extra ticks before escalation (distinguishes noise from anomaly)
NOISE_BAND = 3.0

# Consecutive anomalous ticks required before fault is declared (§5.2, §10.1)
PERSISTENCE_WINDOW = 3

# Ethical autonomy thresholds (§6.3)
ETHICAL = {
    "confidence_high":   0.75,   # ≥ this → full autonomous action allowed
    "confidence_medium": 0.45,   # ≥ this → limited reversible action only
    # < confidence_medium → escalate to human operator
}

# Mission phase (§5.6, §6.1, §6.3)
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

# "upper" = fault when value is too HIGH, "lower" = fault when value is too LOW
POWER_FAULT_DIRECTION = {
    "voltage":     "lower",
    "current":     "upper",
    "soc":         "lower",
    "temperature": "upper",
}

POWER_NOISE_AMPLITUDE = 2.0

# type: "voltage_drop" | "overcurrent" | "battery_drain" | "thermal_overload"
POWER_FAULT_INJECTION_TIMELINE = [
    {
        "tick":        10,
        "type":        "voltage_drop",
        "severity":    "gradual",
        "description": "Primary regulator partial failure — voltage declining",
        "target_value": 30,
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

# type: "thermal_runaway" | "heater_failure" | "radiator_degradation"
THERMAL_FAULT_INJECTION_TIMELINE = [
    {
        "tick":        40,
        "type":        "thermal_runaway",
        "severity":    "gradual",
        "description": "Component bay overheating — thermal control loop degraded",
        "target_value": 88,
    },
]


# ─────────────────────────────────────────────
# BACKWARD COMPATIBILITY ALIASES
# (used by legacy root-level modules)
# ─────────────────────────────────────────────
NOMINAL              = POWER_NOMINAL
ANOMALY_THRESHOLDS   = POWER_THRESHOLDS
NOISE_AMPLITUDE      = POWER_NOISE_AMPLITUDE
FAULT_INJECTION_TIMELINE = POWER_FAULT_INJECTION_TIMELINE


# ─────────────────────────────────────────────
# SYSTEM SETTINGS
# ─────────────────────────────────────────────
TICK_INTERVAL_SECONDS = 1.0
LOG_FILE  = "fdir_event_log.json"
API_HOST  = "0.0.0.0"
API_PORT  = 8000