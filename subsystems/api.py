"""
api.py
======
Ground Station REST API — FastAPI server for sending commands to the spacecraft.

Endpoints:
  ── Status & Telemetry ──────────────────────────────────────────
  GET  /status              Full system state snapshot (all subsystems)
  GET  /health              Health reports for all subsystems
  GET  /health/{subsystem}  Health report for a specific subsystem
  GET  /ping                Health check — is the FDIR system online?

  ── Event Logs ──────────────────────────────────────────────────
  GET  /events              All logged events (with state snapshots)
  GET  /events/recent?n=20  Last N events
  GET  /events/type/{type}  Filter by event type

  ── Ground Commands ─────────────────────────────────────────────
  POST /inject-fault        Inject a fault into a subsystem (demo/testing)
  POST /human-approve       Operator approves a held fault (§6.4)
  POST /mission-phase       Change mission phase (affects ethical decisions)
  POST /reset               Full system reset to nominal

Usage:
  Run via main.py — the FDIR loop starts in a background thread,
  then uvicorn serves this API on http://localhost:8000.

  Interactive docs: http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json
from pathlib import Path

import config as cfg

# Lazy imports — these are set by main.py after the FDIR loop starts
_main = None

def _get_main():
    """Lazy import of main module to avoid circular imports."""
    global _main
    if _main is None:
        import main as _main
    return _main


# ─────────────────────────────────────────────
# FASTAPI APP
# ─────────────────────────────────────────────

app = FastAPI(
    title       = "FDIR Ground Station API",
    description = (
        "Autonomous Fault Detection, Isolation and Recovery System — "
        "Ground Station Command Interface.\n\n"
        "Subsystems: POWER, THERMAL\n\n"
        "Commands: inject faults, approve escalated decisions, "
        "change mission phase, reset system, view telemetry & events."
    ),
    version     = "2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# REQUEST MODELS
# ─────────────────────────────────────────────

class FaultRequest(BaseModel):
    subsystem:    str   = "power"   # "power" | "thermal"
    type:         str               # e.g. "voltage_drop", "thermal_runaway"
    severity:     str   = "gradual" # "gradual" | "sudden"
    description:  str   = "Manual fault injection via ground command"
    target_value: float = 30.0

class ApprovalRequest(BaseModel):
    fault_type:      str            # e.g. "voltage_drop"
    approved_action: str            # e.g. "switch_to_backup_regulator"

class MissionPhaseRequest(BaseModel):
    phase: str                      # "NOMINAL_OPS" | "CRITICAL_MANEUVER" | "COMMS_BLACKOUT" | "SAFE_MODE"


# ─────────────────────────────────────────────
# STATUS & TELEMETRY
# ─────────────────────────────────────────────

@app.get("/status", summary="Full system state snapshot",
         tags=["Telemetry"])
def get_status():
    """Returns the complete current state including all subsystems,
    active faults, recovery status, ethical decisions, and mission phase."""
    m = _get_main()
    with m.state_lock:
        return dict(m.system_state)


@app.get("/health", summary="Health reports for all subsystems",
         tags=["Telemetry"])
def get_health():
    """Returns current health report for every subsystem."""
    m = _get_main()
    with m.state_lock:
        return {
            name: sub["health_report"]
            for name, sub in m.system_state["subsystems"].items()
        }


@app.get("/health/{subsystem}", summary="Health report for one subsystem",
         tags=["Telemetry"])
def get_subsystem_health(subsystem: str):
    """Returns the health report for a specific subsystem (power / thermal)."""
    m = _get_main()
    with m.state_lock:
        subs = m.system_state["subsystems"]
        if subsystem not in subs:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown subsystem '{subsystem}'. Available: {list(subs.keys())}"
            )
        return subs[subsystem]["health_report"]


@app.get("/ping", summary="Health check", tags=["Telemetry"])
def ping():
    """Quick check that the FDIR system is running."""
    m = _get_main()
    with m.state_lock:
        return {
            "status":  "FDIR system online",
            "version": "2.0.0",
            "tick":    m.system_state["tick"],
            "running": m.system_state["running"],
        }


# ─────────────────────────────────────────────
# EVENT LOGS
# ─────────────────────────────────────────────

@app.get("/events", summary="All logged events", tags=["Events"])
def get_all_events():
    """Returns every event logged since system start (or last reset).
    Each event includes a state snapshot for full traceability (§9.1 D4)."""
    try:
        return json.loads(Path(cfg.LOG_FILE).read_text())
    except Exception:
        return []


@app.get("/events/recent", summary="Last N events (default 20)",
         tags=["Events"])
def get_recent_events(n: int = 20):
    """Returns the N most recent events."""
    try:
        events = json.loads(Path(cfg.LOG_FILE).read_text())
        return events[-n:]
    except Exception:
        return []


@app.get("/events/type/{event_type}", summary="Events filtered by type",
         tags=["Events"])
def get_events_by_type(event_type: str):
    """Filter events by type.

    Types: SYSTEM_START, SENSOR_DATA, TEMPORARY_ANOMALY, ANOMALY_DETECTED,
    FAULT_ISOLATED, ETHICAL_DECISION, RECOVERY_ACTION, HUMAN_ESCALATION,
    HUMAN_APPROVAL, FAULT_INJECTED, SAFE_MODE, SYSTEM_NOMINAL, SYSTEM_RESET
    """
    try:
        events = json.loads(Path(cfg.LOG_FILE).read_text())
        return [e for e in events if e.get("event_type") == event_type.upper()]
    except Exception:
        return []


# ─────────────────────────────────────────────
# GROUND COMMANDS
# ─────────────────────────────────────────────

VALID_FAULT_TYPES = {
    "power":   {"voltage_drop", "overcurrent", "battery_drain", "thermal_overload"},
    "thermal": {"thermal_runaway", "heater_failure", "radiator_degradation"},
}

@app.post("/inject-fault",
          summary="Inject a fault into a subsystem (ground command)",
          tags=["Commands"])
def inject_fault(fault: FaultRequest):
    """
    **Ground Command: Fault Injection**

    Injects a fault into the running FDIR loop via a thread-safe queue.
    The fault will be picked up at the next tick.

    **Power fault types:** voltage_drop, overcurrent, battery_drain, thermal_overload

    **Thermal fault types:** thermal_runaway, heater_failure, radiator_degradation

    **Severity:** gradual (realistic drift) or sudden (instant failure)
    """
    m = _get_main()
    subsystem = fault.subsystem.lower()

    if subsystem not in VALID_FAULT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown subsystem '{subsystem}'. Must be one of: {list(VALID_FAULT_TYPES.keys())}"
        )

    if fault.type not in VALID_FAULT_TYPES[subsystem]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid fault type '{fault.type}' for {subsystem}. "
                   f"Must be one of: {VALID_FAULT_TYPES[subsystem]}"
        )

    fault_config = {
        "type":         fault.type,
        "severity":     fault.severity,
        "description":  fault.description,
        "target_value": fault.target_value,
    }

    q = m.fault_queues.get(subsystem)
    if q is None:
        raise HTTPException(status_code=500, detail=f"No queue for subsystem '{subsystem}'")

    q.put(fault_config)

    return {
        "status":    "queued",
        "subsystem": subsystem,
        "message":   f"Fault '{fault.type}' queued for {subsystem} subsystem — will inject at next tick",
        "fault":     fault_config,
    }


@app.post("/human-approve",
          summary="Operator approves a held fault (§6.4)",
          tags=["Commands"])
def human_approve(req: ApprovalRequest):
    """
    **Ground Command: Human Approval**

    §6.4 Human Accountability: When the ethical engine escalates a fault
    to HUMAN_ESCALATION, autonomous action is blocked until the operator
    explicitly approves.

    Call this endpoint to release the hold and allow the FDIR loop to
    proceed with recovery for the specified fault type.
    """
    m = _get_main()

    if m._ethical_engine is None:
        raise HTTPException(status_code=503, detail="FDIR loop not yet started")

    if req.fault_type not in m._ethical_engine.human_hold_faults:
        raise HTTPException(
            status_code=404,
            detail=f"Fault type '{req.fault_type}' is not currently under human hold. "
                   f"Current holds: {list(m._ethical_engine.human_hold_faults)}"
        )

    m._ethical_engine.clear_human_hold(req.fault_type)

    if m._logger:
        m._logger.log_human_approval(
            m._current_tick[0], req.fault_type, req.approved_action
        )

    with m.state_lock:
        m.system_state["human_hold_faults"] = list(m._ethical_engine.human_hold_faults)
        m.system_state["human_alert"] = None

    return {
        "status":          "approved",
        "fault_type":      req.fault_type,
        "approved_action": req.approved_action,
        "message":         f"Human hold cleared for '{req.fault_type}'. "
                           f"FDIR loop will proceed with recovery at next tick.",
    }


@app.post("/mission-phase",
          summary="Change mission phase (affects ethical decisions)",
          tags=["Commands"])
def set_mission_phase(req: MissionPhaseRequest):
    """
    **Ground Command: Mission Phase Change**

    §5.6, §6.1: Changes the active mission phase.
    This directly impacts ethical engine decisions:

    - **NOMINAL_OPS** — full autonomy permitted (LOW criticality)
    - **COMMS_BLACKOUT** — limited autonomy (MEDIUM criticality)
    - **CRITICAL_MANEUVER** — all autonomous action BLOCKED (HIGH criticality)
    - **SAFE_MODE** — all autonomous action BLOCKED (HIGH criticality)
    """
    m = _get_main()
    valid_phases = set(cfg.MISSION_PHASE_CRITICALITY.keys())

    if req.phase not in valid_phases:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid phase '{req.phase}'. Must be one of: {valid_phases}"
        )

    cfg.MISSION_PHASE = req.phase
    criticality = cfg.MISSION_PHASE_CRITICALITY[req.phase]

    with m.state_lock:
        m.system_state["mission_phase"]      = req.phase
        m.system_state["mission_criticality"] = criticality

    return {
        "status":      "updated",
        "phase":       req.phase,
        "criticality": criticality,
        "message":     f"Mission phase set to '{req.phase}' (criticality: {criticality}). "
                       f"Ethical engine will use this for all subsequent decisions.",
    }


@app.post("/reset",
          summary="Full system reset to nominal",
          tags=["Commands"])
def reset_system():
    """
    **Ground Command: System Reset**

    Resets all subsystems, monitors, isolators, ethical holds, recovery state,
    and event logs back to initial nominal conditions.

    The reset takes effect at the next tick.
    """
    m = _get_main()
    m.reset_signal.set()
    return {
        "status":  "reset_queued",
        "message": "System reset will complete at next tick. "
                   "All subsystems, monitors, and logs will be cleared.",
    }