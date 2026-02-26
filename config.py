"""
config.py
=========
Central configuration for the FDIR Power Subsystem.
All thresholds use a normalized 0-100 scale for clarity.

Edit FAULT_INJECTION_TIMELINE and MISSION_PHASE to control demo scenarios.
"""

# ─────────────────────────────────────────────
# SENSOR NOMINAL RANGES (0-100 normalized scale)
# ─────────────────────────────────────────────
NOMINAL = {
    "voltage":     {"min": 45, "max": 75, "nominal": 60},
    "current":     {"min": 20, "max": 60, "nominal": 35},
    "soc":         {"min": 30, "max": 100, "nominal": 80},
    "temperature": {"min": 10, "max": 70,  "nominal": 35},
}

# ─────────────────────────────────────────────
# ANOMALY DETECTION THRESHOLDS
# §5.2: Three-state classification:
#   NOMINAL → no issue
#   WARNING → temporary anomaly (logged, monitoring continues)
#   CRITICAL → persistent confirmed fault (triggers isolation pipeline)
# ─────────────────────────────────────────────
ANOMALY_THRESHOLDS = {
    "voltage":     {"warning": 50, "critical": 38},
    "current":     {"warning": 65, "critical": 78},
    "soc":         {"warning": 35, "critical": 22},
    "temperature": {"warning": 72, "critical": 85},
}

# Noise band around WARNING threshold — readings this close to the threshold
# require extra ticks before escalation (distinguishes noise from anomaly)
NOISE_BAND = 3.0

# Consecutive anomalous ticks required before fault is declared (§5.2, §10.1)
PERSISTENCE_WINDOW = 3

# Simulated sensor noise amplitude (±)
NOISE_AMPLITUDE = 2.0

# ─────────────────────────────────────────────
# ETHICAL AUTONOMY THRESHOLDS (§6.3)
# ─────────────────────────────────────────────
ETHICAL = {
    "confidence_high":   0.75,   # ≥ this → full autonomous action allowed
    "confidence_medium": 0.45,   # ≥ this → limited reversible action only
    # < confidence_medium → escalate to human operator
}

# ─────────────────────────────────────────────
# MISSION PHASE (§5.6, §6.1, §6.3)
# Critical phases force higher confidence requirements & prefer human escalation.
# Options: "NOMINAL_OPS" | "CRITICAL_MANEUVER" | "COMMS_BLACKOUT" | "SAFE_MODE"
# ─────────────────────────────────────────────
MISSION_PHASE = "NOMINAL_OPS"

MISSION_PHASE_CRITICALITY = {
    "NOMINAL_OPS":       "LOW",     # Normal — autonomy preferred
    "COMMS_BLACKOUT":    "MEDIUM",  # No ground contact — autonomy with care
    "CRITICAL_MANEUVER": "HIGH",    # Burns/docking — human must approve
    "SAFE_MODE":         "HIGH",    # Already degraded — conservative
}

# ─────────────────────────────────────────────
# FAULT INJECTION TIMELINE
# type options: "voltage_drop" | "overcurrent" | "battery_drain" | "thermal_overload"
# severity: "gradual" | "sudden"
# ─────────────────────────────────────────────
FAULT_INJECTION_TIMELINE = [
    {
        "tick":        10,
        "type":        "voltage_drop",
        "severity":    "gradual",
        "description": "Primary regulator partial failure — voltage declining",
        "target_value": 30,
    },
    # {
    #     "tick":        35,
    #     "type":        "overcurrent",
    #     "severity":    "sudden",
    #     "description": "Current spike on primary bus",
    #     "target_value": 85,
    # },
    # {
    #     "tick":        60,
    #     "type":        "battery_drain",
    #     "severity":    "gradual",
    #     "description": "Battery SoC draining abnormally fast",
    #     "target_value": 18,
    # },
    # {
    #     "tick":        85,
    #     "type":        "thermal_overload",
    #     "severity":    "sudden",
    #     "description": "Regulator temperature spike",
    #     "target_value": 92,
    # },
]

# ─────────────────────────────────────────────
# SYSTEM SETTINGS
# ─────────────────────────────────────────────
TICK_INTERVAL_SECONDS = 1.0
LOG_FILE  = "fdir_event_log.json"
API_HOST  = "0.0.0.0"
API_PORT  = 8000