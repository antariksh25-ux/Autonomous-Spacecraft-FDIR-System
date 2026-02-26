"""
main.py
=======
FDIR Power Subsystem — Main Entry Point

Runs simultaneously:
1. FDIR SCENARIO LOOP — full pipeline every tick with full exception handling
2. FASTAPI REST SERVER — all endpoints your frontend teammate needs

Fixed gaps from v1:
  ✓ /inject-fault API actually injects into running loop (via queue)
  ✓ /reset endpoint implemented (full system reset)
  ✓ /human-approve endpoint (clears human hold — §6.4)
  ✓ /mission-phase endpoint (change mission phase live)
  ✓ safe_mode triggered from main loop if system remains CRITICAL post-recovery
  ✓ human_hold state prevents further autonomous action on escalated faults (§6.4)
  ✓ exception handling wraps every tick — demo never crashes (§10.3)
  ✓ temporary anomalies surfaced in status (§5.2)
  ✓ mission_criticality present in all state/events (§6.1)
"""

import time
import queue
import threading
# import uvicorn
# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

import config as cfg
from simulator      import PowerSubsystemSimulator
from health_monitor import HealthMonitor, HealthStatus
from fault_isolator import FaultIsolator
from ethical_engine import EthicalEngine, AutonomyDecision
from recovery       import RecoveryModule
from logger         import FDIRLogger, EventType


# ─────────────────────────────────────────────
# FAULT INJECTION QUEUE (thread-safe API → loop communication)
# ─────────────────────────────────────────────
fault_injection_queue: queue.Queue = queue.Queue()

# ─────────────────────────────────────────────
# SHARED SYSTEM STATE
# ─────────────────────────────────────────────
system_state = {
    "running":             False,
    "tick":                0,
    "sensor_data":         {},
    "health_report":       {},
    "last_diagnosis":      None,
    "last_ethical":        None,
    "last_recovery":       None,
    "system_status":       "INITIALIZING",
    "overall_status":      "INITIALIZING",
    "active_faults":       [],
    "temporary_anomalies": [],
    "recovery_active":     False,
    "safe_mode_active":    False,
    "human_alert":         None,
    "human_hold_faults":   [],
    "mission_phase":       cfg.MISSION_PHASE,
    "mission_criticality": cfg.MISSION_PHASE_CRITICALITY.get(cfg.MISSION_PHASE, "LOW"),
}
state_lock = threading.Lock()

# Reset signal — set True by /reset endpoint
reset_signal = threading.Event()

# Global module references (set once loop starts, needed by human-approve endpoint)
_ethical_engine: Optional[EthicalEngine] = None
_logger: Optional[FDIRLogger] = None
_current_tick = [0]   # mutable container for tick count across threads


def build_state_snapshot(sensor_data: dict, health_report: dict) -> dict:
    """Build a compact state snapshot for event logging (§9.1 D4)."""
    return {
        "sensor_data":   sensor_data,
        "overall_status": health_report.get("overall_status", "UNKNOWN"),
        "confirmed_anomalies": health_report.get("confirmed_anomalies", []),
        "mission_phase": cfg.MISSION_PHASE,
    }


# ─────────────────────────────────────────────
# FDIR PIPELINE LOOP
# ─────────────────────────────────────────────

def run_fdir_scenario():
    global _ethical_engine, _logger

    simulator = PowerSubsystemSimulator()
    monitor   = HealthMonitor()
    isolator  = FaultIsolator()
    ethical   = EthicalEngine()
    recovery  = RecoveryModule(simulator)
    logger    = FDIRLogger()

    _ethical_engine = ethical
    _logger         = logger

    # Build fault injection timeline lookup: tick → fault config
    fault_timeline = {f["tick"]: f for f in cfg.FAULT_INJECTION_TIMELINE}

    # Track handled faults to prevent oscillation (§10.2)
    handled_fault_types: set = set()
    last_injection_tick: int = -99  # suppress nominal log right after injection

    # Track if safe mode was triggered (post-recovery escalation)
    safe_mode_triggered = False
    nominal_reported    = False

    # Track ticks since recovery started (for safe mode escalation)
    recovery_tick_counter: dict = {}   # fault_type → ticks since recovery

    logger.log_system_start(cfg.MISSION_PHASE)

    with state_lock:
        system_state["running"]           = True
        system_state["mission_phase"]     = cfg.MISSION_PHASE
        system_state["mission_criticality"] = cfg.MISSION_PHASE_CRITICALITY.get(cfg.MISSION_PHASE, "LOW")

    tick = 0

    while True:
        # ── Check reset signal ──────────────────────────────────────
        if reset_signal.is_set():
            reset_signal.clear()
            simulator.reset()
            monitor.reset_all()
            isolator.reset()
            ethical.clear_all_holds()
            recovery.reset()
            logger.clear()
            logger.log_system_reset()
            fault_timeline   = {f["tick"]: f for f in cfg.FAULT_INJECTION_TIMELINE}
            handled_fault_types.clear()
            recovery_tick_counter.clear()
            safe_mode_triggered = False
            nominal_reported    = False
            tick = 0
            with state_lock:
                system_state.update({
                    "tick":                0,
                    "sensor_data":         {},
                    "health_report":       {},
                    "last_diagnosis":      None,
                    "last_ethical":        None,
                    "last_recovery":       None,
                    "system_status":       "NOMINAL",
                    "overall_status":      "NOMINAL",
                    "active_faults":       [],
                    "temporary_anomalies": [],
                    "recovery_active":     False,
                    "safe_mode_active":    False,
                    "human_alert":         None,
                    "human_hold_faults":   [],
                    "mission_phase":       cfg.MISSION_PHASE,
                    "mission_criticality": cfg.MISSION_PHASE_CRITICALITY.get(cfg.MISSION_PHASE, "LOW"),
                })

        tick += 1
        _current_tick[0] = tick
        time.sleep(cfg.TICK_INTERVAL_SECONDS)

        try:   # §10.3: Exception handling — loop never crashes demo

            # ── API fault injections (from /inject-fault endpoint) ──
            while not fault_injection_queue.empty():
                api_fault = fault_injection_queue.get_nowait()
                api_fault["tick"] = tick   # assign current tick
                simulator.inject_fault(api_fault)
                logger.log_fault_injected(tick, api_fault)
                handled_fault_types.discard(api_fault["type"])
                nominal_reported = False
                last_injection_tick = tick

            # ── Timeline fault injections (from config) ─────────────
            if tick in fault_timeline:
                fault_config = fault_timeline[tick]
                simulator.inject_fault(fault_config)
                logger.log_fault_injected(tick, fault_config)
                handled_fault_types.discard(fault_config["type"])
                nominal_reported = False
                last_injection_tick = tick

            # ── STEP 1: Sensor Data ─────────────────────────────────
            sensor_data = simulator.tick()
            logger.log_sensor_data(tick, sensor_data)

            # ── STEP 2: Health Monitoring ───────────────────────────
            health_report = monitor.process(sensor_data)
            snapshot = build_state_snapshot(sensor_data, health_report)

            with state_lock:
                system_state["tick"]           = tick
                system_state["sensor_data"]    = sensor_data
                system_state["overall_status"] = health_report["overall_status"]
                system_state["system_status"]  = health_report["overall_status"]
                system_state["temporary_anomalies"] = health_report["temporary_anomalies"]
                system_state["health_report"]  = {
                    "overall_status":      health_report["overall_status"],
                    "confirmed_anomalies": health_report["confirmed_anomalies"],
                    "temporary_anomalies": health_report["temporary_anomalies"],
                    "has_anomaly":         health_report["has_anomaly"],
                    "has_temporary":       health_report["has_temporary"],
                    "parameters": {
                        k: {"value": v["value"], "status": v["status"]}
                        for k, v in health_report["parameters"].items()
                    },
                }

            # ── Log temporary anomalies (§5.2 distinct state) ───────
            # Only when there's a temporary anomaly but NO confirmed fault yet
            if health_report["has_temporary"] and not health_report["has_anomaly"]:
                logger.log_temporary_anomaly(tick, health_report)

            # ── No confirmed anomaly — nominal or recovering ────────
            if not health_report["has_anomaly"]:
                # Increment recovery counters and log recovery-in-progress once
                recovery_logged_this_tick = False
                for ft in list(recovery_tick_counter.keys()):
                    recovery_tick_counter[ft] += 1
                    if recovery_tick_counter[ft] == 1:
                        logger.log_recovery_in_progress(tick, ft)
                        recovery_logged_this_tick = True

                # Log nominal only when truly stable
                ticks_since_injection = tick - last_injection_tick
                if (not nominal_reported and tick > 5
                        and ticks_since_injection > 3
                        and not recovery_logged_this_tick):
                    logger.log_system_nominal(tick)
                    nominal_reported = True
                with state_lock:
                    system_state["recovery_active"]  = simulator.recovery_mode
                    system_state["safe_mode_active"]  = recovery.safe_mode_active
                    system_state["human_alert"]       = None
                    system_state["human_hold_faults"] = list(ethical.human_hold_faults)
                continue

            # ── Confirmed anomaly — run isolation pipeline ───────────
            nominal_reported = False

            # Guard: only proceed if confirmed_anomalies is non-empty
            if not health_report["confirmed_anomalies"]:
                continue

            # ── STEP 3: Fault Isolation ─────────────────────────────
            diagnosis = isolator.isolate(health_report)
            if diagnosis is None:
                # Anomaly detected but doesn't match any known fault signature
                logger.log_anomaly(tick, health_report, snapshot)
                continue

            # If already handled — recovery in progress, pipeline blocked (§10.2)
            if diagnosis.fault_type in handled_fault_types:
                # Increment counter and log once while sensor is still in anomaly range
                recovery_tick_counter[diagnosis.fault_type] = recovery_tick_counter.get(diagnosis.fault_type, 0) + 1
                if recovery_tick_counter[diagnosis.fault_type] == 1:
                    logger.log_recovery_in_progress(tick, diagnosis.fault_type)
                continue

            # If under human hold — log anomaly but block pipeline (§6.4)
            if ethical.is_under_human_hold(diagnosis.fault_type):
                logger.log_anomaly(tick, health_report, snapshot)
                with state_lock:
                    system_state["human_hold_faults"] = list(ethical.human_hold_faults)
                continue

            # New unhandled fault — log anomaly and proceed through pipeline
            logger.log_anomaly(tick, health_report, snapshot)

            diagnosis_dict = isolator.to_dict(diagnosis)
            logger.log_fault_isolation(tick, diagnosis_dict, snapshot)

            with state_lock:
                system_state["last_diagnosis"] = diagnosis_dict
                system_state["active_faults"]  = [diagnosis.fault_type]

            # ── STEP 4: Ethical Autonomy Evaluation ─────────────────
            ethical_decision = ethical.evaluate(diagnosis)
            ethical_dict     = ethical.to_dict(ethical_decision)
            logger.log_ethical_decision(tick, ethical_dict, snapshot)

            with state_lock:
                system_state["last_ethical"]      = ethical_dict
                system_state["human_hold_faults"] = list(ethical.human_hold_faults)
                system_state["mission_phase"]     = ethical_dict["mission_phase"]
                system_state["mission_criticality"] = ethical_dict["mission_criticality"]

            # ── STEP 5: Recovery or Escalation ──────────────────────
            if ethical_decision.autonomy_level == AutonomyDecision.HUMAN_ESCALATION:
                logger.log_human_escalation(tick, ethical_decision.human_message, snapshot)
                with state_lock:
                    system_state["human_alert"]       = ethical_decision.human_message
                    system_state["human_hold_faults"] = list(ethical.human_hold_faults)
                # NOTE: handled_fault_types NOT updated — allows re-evaluation
                # when human clears hold via /human-approve

            else:
                recovery_result = recovery.execute(ethical_decision)
                recovery_dict   = recovery.to_dict(recovery_result)
                logger.log_recovery(tick, recovery_dict, snapshot)

                with state_lock:
                    system_state["last_recovery"]   = recovery_dict
                    system_state["recovery_active"]  = True
                    system_state["safe_mode_active"] = recovery.safe_mode_active
                    system_state["human_alert"]      = (
                        ethical_dict["human_message"] or None
                    )

                # Do NOT reset health monitor here — sensor may still be recovering.
                # Clearing history now causes the anomaly to re-confirm next tick.
                # Monitor naturally returns to NOMINAL as sensor values recover.
                handled_fault_types.add(diagnosis.fault_type)
                recovery_tick_counter[diagnosis.fault_type] = 0

            # ── STEP 6: Safe Mode escalation (§5.5 last resort) ─────
            # If system is still CRITICAL after PERSISTENCE_WINDOW ticks of recovery
            # and safe mode hasn't been triggered yet, escalate (§5.5)
            if (recovery.is_recovering
                    and not safe_mode_triggered
                    and health_report["overall_status"] == HealthStatus.CRITICAL):
                for ft, counter in list(recovery_tick_counter.items()):
                    if counter > PERSISTENCE_WINDOW + 3:   # grace period
                        safe_mode_triggered = True
                        sm_result = recovery.trigger_safe_mode()
                        logger.log_safe_mode(
                            tick,
                            f"System remained CRITICAL for {counter} ticks post-recovery — "
                            f"escalating to safe mode for mission survivability (§5.5)"
                        )
                        logger.log_recovery(tick, recovery.to_dict(sm_result), snapshot)
                        with state_lock:
                            system_state["safe_mode_active"] = True
                        break

            # Update recovery counters
            for ft in list(recovery_tick_counter.keys()):
                recovery_tick_counter[ft] += 1

        except Exception as e:
            # §10.3: Never crash the demo loop — log and continue
            print(f"\n[ERROR] Tick {tick} exception (loop continues): {e}")
            import traceback
            traceback.print_exc()


# Import after defining PERSISTENCE_WINDOW usage
PERSISTENCE_WINDOW = cfg.PERSISTENCE_WINDOW


# ─────────────────────────────────────────────
# FASTAPI SERVER
# ─────────────────────────────────────────────
# app = FastAPI(
#     title       = "FDIR Power Subsystem API",
#     description = (
#         "Autonomous Fault Detection, Isolation and Recovery System — Power Subsystem. "
#         "Endpoints expose real-time system state, event logs, and operator controls."
#     ),
#     version     = "2.0.0",
# )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"], allow_credentials=True,
#     allow_methods=["*"], allow_headers=["*"],
# )


# ── Status & Health ─────────────────────────────────────────────

# @app.get("/status", summary="Full current system state snapshot")
# def get_status():
#     with state_lock:
#         return dict(system_state)


# @app.get("/health", summary="Current health report only")
# def get_health():
#     with state_lock:
#         return system_state["health_report"]


# @app.get("/ping", summary="Health check")
# def ping():
#     return {"status": "FDIR system online", "version": "2.0.0"}


# ── Event Logs ──────────────────────────────────────────────────

# @app.get("/events", summary="All logged events with state snapshots")
# def get_all_events():
#     import json
#     from pathlib import Path
#     try:
#         return json.loads(Path(cfg.LOG_FILE).read_text())
#     except Exception:
#         return []


# @app.get("/events/recent", summary="Last N events (default 20)")
# def get_recent_events(n: int = 20):
#     import json
#     from pathlib import Path
#     try:
#         events = json.loads(Path(cfg.LOG_FILE).read_text())
#         return events[-n:]
#     except Exception:
#         return []


# @app.get("/events/type/{event_type}", summary="Events filtered by type")
# def get_events_by_type(event_type: str):
#     import json
#     from pathlib import Path
#     try:
#         events = json.loads(Path(cfg.LOG_FILE).read_text())
#         return [e for e in events if e.get("event_type") == event_type.upper()]
#     except Exception:
#         return []


# ── Fault Injection ─────────────────────────────────────────────

class FaultRequest(BaseModel):
    type:         str
    severity:     str   = "gradual"
    description:  str   = "Manual fault injection via API"
    target_value: float = 30.0


# @app.post("/inject-fault", summary="Inject a fault into the live running system")
# def inject_fault_api(fault: FaultRequest):
#     """
#     Injects a fault into the running FDIR loop via thread-safe queue.
#     Frontend teammate can call this to trigger demo scenarios on demand.

#     type options: voltage_drop | overcurrent | battery_drain | thermal_overload
#     severity:     gradual | sudden
#     """
#     valid_types = {"voltage_drop", "overcurrent", "battery_drain", "thermal_overload"}
#     if fault.type not in valid_types:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Invalid fault type. Must be one of: {valid_types}"
#         )

#     fault_config = fault.dict()
#     fault_injection_queue.put(fault_config)
#     return {
#         "status":  "queued",
#         "message": f"Fault '{fault.type}' queued for injection at next tick",
#         "fault":   fault_config,
#     }


# ── Human Operator Controls ──────────────────────────────────────

class ApprovalRequest(BaseModel):
    fault_type:      str
    approved_action: str   # e.g. "switch_to_backup_regulator"


# @app.post("/human-approve", summary="§6.4 Human operator approves and clears hold on a fault")
# def human_approve(req: ApprovalRequest):
#     """
#     §6.4 Human Accountability: Releases the autonomous action hold on a fault.
#     After this, the FDIR loop can proceed with recovery for this fault type.

#     Call this when the operator reviews an escalated fault and approves action.
#     """
#     if _ethical_engine is None:
#         raise HTTPException(status_code=503, detail="FDIR loop not yet started")

#     _ethical_engine.clear_human_hold(req.fault_type)

#     if _logger:
#         _logger.log_human_approval(
#             _current_tick[0], req.fault_type, req.approved_action
#         )

#     with state_lock:
#         system_state["human_hold_faults"] = list(_ethical_engine.human_hold_faults)
#         system_state["human_alert"] = None

#     return {
#         "status":          "approved",
#         "fault_type":      req.fault_type,
#         "approved_action": req.approved_action,
#         "message":         f"Human hold cleared for '{req.fault_type}'. "
#                            f"FDIR loop will proceed with recovery.",
#     }


class MissionPhaseRequest(BaseModel):
    phase: str   # "NOMINAL_OPS" | "CRITICAL_MANEUVER" | "COMMS_BLACKOUT" | "SAFE_MODE"


# @app.post("/mission-phase", summary="Change the current mission phase (affects ethical decisions)")
# def set_mission_phase(req: MissionPhaseRequest):
#     """
#     §5.6, §6.1: Changes mission phase. This directly affects ethical engine decisions.
#     During CRITICAL_MANEUVER — all autonomous action is blocked regardless of confidence.
#     """
#     valid_phases = set(cfg.MISSION_PHASE_CRITICALITY.keys())
#     if req.phase not in valid_phases:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Invalid phase. Must be one of: {valid_phases}"
#         )
#     cfg.MISSION_PHASE = req.phase
#     criticality = cfg.MISSION_PHASE_CRITICALITY[req.phase]
#     with state_lock:
#         system_state["mission_phase"]     = req.phase
#         system_state["mission_criticality"] = criticality
#     return {
#         "status":      "updated",
#         "phase":       req.phase,
#         "criticality": criticality,
#         "message":     f"Mission phase set to '{req.phase}' (criticality: {criticality})",
#     }


# @app.post("/reset", summary="Full system reset — clears all state and restarts from nominal")
# def reset_system():
#     """Resets simulator, monitors, logs, and all internal state to nominal."""
#     reset_signal.set()
#     return {"status": "reset_queued", "message": "System reset will complete at next tick"}


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
# if __name__ == "__main__":
#     # Start FDIR scenario loop in background thread
#     scenario_thread = threading.Thread(target=run_fdir_scenario, daemon=True)
#     scenario_thread.start()

#     print("\n[FDIR] FastAPI server starting...")
#     print(f"[FDIR] API:     http://localhost:{cfg.API_PORT}")
#     print(f"[FDIR] Docs:    http://localhost:{cfg.API_PORT}/docs")
#     print(f"[FDIR] Events:  http://localhost:{cfg.API_PORT}/events\n")

#     uvicorn.run(app, host=cfg.API_HOST, port=cfg.API_PORT, log_level="warning")

if __name__ == "__main__":
    run_fdir_scenario()   # runs directly in main thread, no server