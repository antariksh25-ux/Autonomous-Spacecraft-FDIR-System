"""
main.py
=======
FDIR Multi-Subsystem — Main Entry Point

Orchestrates the full FDIR pipeline for all registered subsystems every tick:
  Sensor → Monitor → Isolate → Ethical Gate → Recovery

Supported subsystems: POWER, THERMAL

Features:
  ✓ Per-subsystem fault injection timelines + API queues
  ✓ Cross-coupling: power current feeds into thermal simulator
  ✓ Per-subsystem handled-fault tracking (§10.2 anti-oscillation)
  ✓ Shared ethical engine + recovery module (subsystem-agnostic)
  ✓ Safe mode escalation across all subsystems (§5.5)
  ✓ Exception handling wraps every tick — demo never crashes (§10.3)
"""

import sys
import os
import time
import queue
import threading

# Ensure club/ directory is on sys.path for package imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Fix double-import: when run as `python main.py`, the module is "__main__".
# api.py does `import main` which would create a SECOND copy with separate state.
# This alias ensures both names point to the same module instance.
if __name__ == "__main__":
    sys.modules["main"] = sys.modules["__main__"]

import config as cfg
from subsystems.base import (
    HealthStatus,
    FaultDiagnosis,
    SubsystemMonitor,
    SubsystemIsolator,
)
from subsystems.power.simulator import PowerSubsystemSimulator
from subsystems.power.isolator import POWER_FAULT_SIGNATURES
from subsystems.thermal.simulator import ThermalSubsystemSimulator
from subsystems.thermal.isolator import THERMAL_FAULT_SIGNATURES
from ethical_engine import EthicalEngine, AutonomyDecision
from recovery import RecoveryModule
from logger import FDIRLogger, EventType


# ─────────────────────────────────────────────
# FAULT INJECTION QUEUES (thread-safe, per-subsystem)
# ─────────────────────────────────────────────
fault_queues = {
    "power":   queue.Queue(),
    "thermal": queue.Queue(),
}

# ─────────────────────────────────────────────
# SHARED SYSTEM STATE
# ─────────────────────────────────────────────
system_state = {
    "running":             False,
    "tick":                0,
    "subsystems": {
        "power":   {"sensor_data": {}, "health_report": {}, "last_diagnosis": None, "status": "INITIALIZING"},
        "thermal": {"sensor_data": {}, "health_report": {}, "last_diagnosis": None, "status": "INITIALIZING"},
    },
    "last_ethical":        None,
    "last_recovery":       None,
    "overall_status":      "INITIALIZING",
    "active_faults":       [],
    "recovery_active":     False,
    "safe_mode_active":    False,
    "human_alert":         None,
    "human_hold_faults":   [],
    "mission_phase":       cfg.MISSION_PHASE,
    "mission_criticality": cfg.MISSION_PHASE_CRITICALITY.get(cfg.MISSION_PHASE, "LOW"),
}
state_lock = threading.Lock()
reset_signal = threading.Event()

_ethical_engine = None
_logger = None
_current_tick = [0]


STATUS_PRIORITY = [HealthStatus.CRITICAL, HealthStatus.WARNING,
                   HealthStatus.TEMPORARY_ANOMALY, HealthStatus.NOMINAL]

def _worst_status(statuses: list) -> str:
    for s in STATUS_PRIORITY:
        if s in statuses:
            return s
    return HealthStatus.NOMINAL


def build_state_snapshot(all_sensor_data: dict, all_health: dict) -> dict:
    return {
        "sensor_data": all_sensor_data,
        "health": {
            name: {
                "overall_status": h.get("overall_status", "UNKNOWN"),
                "confirmed_anomalies": h.get("confirmed_anomalies", []),
            }
            for name, h in all_health.items()
        },
        "mission_phase": cfg.MISSION_PHASE,
    }


# ─────────────────────────────────────────────
# FDIR PIPELINE LOOP
# ─────────────────────────────────────────────

def run_fdir_scenario():
    global _ethical_engine, _logger

    # ── Initialize subsystem components ──────────────────────────
    power_sim   = PowerSubsystemSimulator()
    thermal_sim = ThermalSubsystemSimulator()

    power_mon = SubsystemMonitor(
        "power", cfg.POWER_NOMINAL, cfg.POWER_THRESHOLDS,
        cfg.POWER_FAULT_DIRECTION, cfg.PERSISTENCE_WINDOW, cfg.NOISE_BAND,
    )
    thermal_mon = SubsystemMonitor(
        "thermal", cfg.THERMAL_NOMINAL, cfg.THERMAL_THRESHOLDS,
        cfg.THERMAL_FAULT_DIRECTION, cfg.PERSISTENCE_WINDOW, cfg.NOISE_BAND,
    )

    power_iso   = SubsystemIsolator("power", POWER_FAULT_SIGNATURES)
    thermal_iso = SubsystemIsolator("thermal", THERMAL_FAULT_SIGNATURES)

    ethical  = EthicalEngine()
    recovery = RecoveryModule({"power": power_sim, "thermal": thermal_sim})
    logger   = FDIRLogger()

    _ethical_engine = ethical
    _logger = logger

    # ── Bundle subsystems for iteration ─────────────────────────
    subs = {
        "power": {
            "simulator": power_sim,
            "monitor":   power_mon,
            "isolator":  power_iso,
            "timeline":  {f["tick"]: f for f in cfg.POWER_FAULT_INJECTION_TIMELINE},
            "handled_faults":    set(),
            "recovery_counters": {},
            "health":   {},
        },
        "thermal": {
            "simulator": thermal_sim,
            "monitor":   thermal_mon,
            "isolator":  thermal_iso,
            "timeline":  {f["tick"]: f for f in cfg.THERMAL_FAULT_INJECTION_TIMELINE},
            "handled_faults":    set(),
            "recovery_counters": {},
            "health":   {},
        },
    }

    safe_mode_triggered = False
    nominal_reported    = False
    last_injection_tick = -99

    logger.log_system_start(cfg.MISSION_PHASE, list(subs.keys()))

    with state_lock:
        system_state["running"]           = True
        system_state["mission_phase"]     = cfg.MISSION_PHASE
        system_state["mission_criticality"] = cfg.MISSION_PHASE_CRITICALITY.get(cfg.MISSION_PHASE, "LOW")

    tick = 0

    while True:
        # ── Check reset signal ──────────────────────────────────
        if reset_signal.is_set():
            reset_signal.clear()
            for name, sub in subs.items():
                sub["simulator"].reset()
                sub["monitor"].reset_all()
                sub["isolator"].reset()
                sub["handled_faults"].clear()
                sub["recovery_counters"].clear()
                tl_cfg = (cfg.POWER_FAULT_INJECTION_TIMELINE if name == "power"
                          else cfg.THERMAL_FAULT_INJECTION_TIMELINE)
                sub["timeline"] = {f["tick"]: f for f in tl_cfg}
            ethical.clear_all_holds()
            recovery.reset()
            logger.clear()
            logger.log_system_reset()
            safe_mode_triggered = False
            nominal_reported    = False
            tick = 0
            with state_lock:
                system_state.update({
                    "tick": 0, "overall_status": "NOMINAL",
                    "active_faults": [], "recovery_active": False,
                    "safe_mode_active": False, "human_alert": None,
                    "human_hold_faults": [], "last_ethical": None, "last_recovery": None,
                })
                for name in subs:
                    system_state["subsystems"][name] = {
                        "sensor_data": {}, "health_report": {},
                        "last_diagnosis": None, "status": "NOMINAL",
                    }

        tick += 1
        _current_tick[0] = tick
        time.sleep(cfg.TICK_INTERVAL_SECONDS)

        try:   # §10.3: Exception handling — loop never crashes demo

            # ══════════════════════════════════════════════════════
            # STEP 1:  FAULT INJECTION (timeline + API, all subs)
            # ══════════════════════════════════════════════════════
            for name, sub in subs.items():
                # API queue
                q = fault_queues.get(name)
                if q:
                    while not q.empty():
                        api_fault = q.get_nowait()
                        api_fault["tick"] = tick
                        sub["simulator"].inject_fault(api_fault)
                        logger.log_fault_injected(tick, name, api_fault)
                        sub["handled_faults"].discard(api_fault["type"])
                        nominal_reported = False
                        last_injection_tick = tick

                # Timeline
                if tick in sub["timeline"]:
                    fc = sub["timeline"][tick]
                    sub["simulator"].inject_fault(fc)
                    logger.log_fault_injected(tick, name, fc)
                    sub["handled_faults"].discard(fc["type"])
                    nominal_reported = False
                    last_injection_tick = tick

            # ══════════════════════════════════════════════════════
            # STEP 2:  SENSOR DATA GENERATION
            # ══════════════════════════════════════════════════════
            power_data   = subs["power"]["simulator"].tick()
            thermal_data = subs["thermal"]["simulator"].tick(
                power_current=power_data.get("current"),
            )
            all_sensor = {"power": power_data, "thermal": thermal_data}
            logger.log_sensor_data(tick, all_sensor)

            # ══════════════════════════════════════════════════════
            # STEP 3:  HEALTH MONITORING
            # ══════════════════════════════════════════════════════
            for name, sub in subs.items():
                sub["health"] = sub["monitor"].process(all_sensor[name])

            all_health = {name: sub["health"] for name, sub in subs.items()}
            snapshot   = build_state_snapshot(all_sensor, all_health)

            # Update shared state
            with state_lock:
                system_state["tick"] = tick
                statuses = []
                for name, sub in subs.items():
                    h = sub["health"]
                    statuses.append(h["overall_status"])
                    system_state["subsystems"][name]["sensor_data"]    = all_sensor[name]
                    system_state["subsystems"][name]["status"]         = h["overall_status"]
                    system_state["subsystems"][name]["health_report"]  = {
                        "overall_status":      h["overall_status"],
                        "confirmed_anomalies": h["confirmed_anomalies"],
                        "temporary_anomalies": h["temporary_anomalies"],
                        "has_anomaly":         h["has_anomaly"],
                        "has_temporary":       h["has_temporary"],
                        "parameters": {
                            k: {"value": v["value"], "status": v["status"]}
                            for k, v in h["parameters"].items()
                        },
                    }
                system_state["overall_status"] = _worst_status(statuses)

            # ── Log temporary anomalies (§5.2) ──────────────────
            for name, sub in subs.items():
                h = sub["health"]
                if h["has_temporary"] and not h["has_anomaly"]:
                    logger.log_temporary_anomaly(tick, name, h)

            # ══════════════════════════════════════════════════════
            # STEP 4:  NO-ANOMALY PATH (nominal or recovering)
            # ══════════════════════════════════════════════════════
            any_anomaly = any(sub["health"]["has_anomaly"] for sub in subs.values())

            if not any_anomaly:
                recovery_logged = False
                for name, sub in subs.items():
                    for ft in list(sub["recovery_counters"].keys()):
                        sub["recovery_counters"][ft] += 1
                        if sub["recovery_counters"][ft] == 1:
                            logger.log_recovery_in_progress(tick, name, ft)
                            recovery_logged = True

                ticks_since = tick - last_injection_tick
                if (not nominal_reported and tick > 5
                        and ticks_since > 3 and not recovery_logged):
                    logger.log_system_nominal(tick)
                    nominal_reported = True

                with state_lock:
                    system_state["recovery_active"]  = any(
                        s["simulator"].recovery_mode for s in subs.values()
                    )
                    system_state["safe_mode_active"]  = recovery.safe_mode_active
                    system_state["human_alert"]       = None
                    system_state["human_hold_faults"] = list(ethical.human_hold_faults)
                continue

            # ══════════════════════════════════════════════════════
            # STEP 5:  FAULT PIPELINE (per subsystem with anomaly)
            # ══════════════════════════════════════════════════════
            nominal_reported = False

            for name, sub in subs.items():
                h = sub["health"]
                if not h["has_anomaly"] or not h["confirmed_anomalies"]:
                    # This subsystem is fine — still increment its recovery counters
                    for ft in list(sub["recovery_counters"].keys()):
                        sub["recovery_counters"][ft] += 1
                        if sub["recovery_counters"][ft] == 1:
                            logger.log_recovery_in_progress(tick, name, ft)
                    continue

                # ── Fault Isolation ──────────────────────────────
                diagnosis = sub["isolator"].isolate(h)
                if diagnosis is None:
                    logger.log_anomaly(tick, name, h, snapshot)
                    continue

                # Already handled → recovery in progress (§10.2)
                if diagnosis.fault_type in sub["handled_faults"]:
                    counter = sub["recovery_counters"].get(diagnosis.fault_type, 0) + 1
                    sub["recovery_counters"][diagnosis.fault_type] = counter
                    if counter == 1:
                        logger.log_recovery_in_progress(tick, name, diagnosis.fault_type)
                    continue

                # Under human hold (§6.4)
                if ethical.is_under_human_hold(diagnosis.fault_type):
                    logger.log_anomaly(tick, name, h, snapshot)
                    with state_lock:
                        system_state["human_hold_faults"] = list(ethical.human_hold_faults)
                    continue

                # ── New unhandled fault — full pipeline ──────────
                logger.log_anomaly(tick, name, h, snapshot)

                diag_dict = SubsystemIsolator.to_dict(diagnosis)
                logger.log_fault_isolation(tick, name, diag_dict, snapshot)

                with state_lock:
                    system_state["subsystems"][name]["last_diagnosis"] = diag_dict
                    if f"{name}:{diagnosis.fault_type}" not in system_state["active_faults"]:
                        system_state["active_faults"].append(f"{name}:{diagnosis.fault_type}")

                # ── Ethical Autonomy Evaluation ───────────────────
                ethical_decision = ethical.evaluate(diagnosis)
                ethical_dict     = ethical.to_dict(ethical_decision)
                logger.log_ethical_decision(tick, ethical_dict, snapshot)

                with state_lock:
                    system_state["last_ethical"]       = ethical_dict
                    system_state["human_hold_faults"]  = list(ethical.human_hold_faults)
                    system_state["mission_phase"]      = ethical_dict["mission_phase"]
                    system_state["mission_criticality"] = ethical_dict["mission_criticality"]

                # ── Recovery or Escalation ────────────────────────
                if ethical_decision.autonomy_level == AutonomyDecision.HUMAN_ESCALATION:
                    logger.log_human_escalation(tick, ethical_decision.human_message, snapshot)
                    with state_lock:
                        system_state["human_alert"]       = ethical_decision.human_message
                        system_state["human_hold_faults"] = list(ethical.human_hold_faults)
                else:
                    recovery_result = recovery.execute(ethical_decision, name)
                    recovery_dict   = recovery.to_dict(recovery_result)
                    logger.log_recovery(tick, name, recovery_dict, snapshot)

                    with state_lock:
                        system_state["last_recovery"]   = recovery_dict
                        system_state["recovery_active"]  = True
                        system_state["safe_mode_active"] = recovery.safe_mode_active
                        system_state["human_alert"]      = (
                            ethical_dict.get("human_message") or None
                        )

                    sub["handled_faults"].add(diagnosis.fault_type)
                    sub["recovery_counters"][diagnosis.fault_type] = 0

            # ══════════════════════════════════════════════════════
            # STEP 6:  SAFE MODE ESCALATION (§5.5 last resort)
            # ══════════════════════════════════════════════════════
            any_recovering = any(s["simulator"].recovery_mode for s in subs.values())
            if any_recovering and not safe_mode_triggered:
                for name, sub in subs.items():
                    h = sub["health"]
                    if h["overall_status"] == HealthStatus.CRITICAL:
                        for ft, counter in list(sub["recovery_counters"].items()):
                            if counter > cfg.PERSISTENCE_WINDOW + 3:
                                safe_mode_triggered = True
                                sm_result = recovery.trigger_safe_mode()
                                logger.log_safe_mode(
                                    tick,
                                    f"[{name.upper()}] Remained CRITICAL for {counter} ticks "
                                    f"post-recovery — escalating to safe mode (§5.5)"
                                )
                                logger.log_recovery(tick, name, recovery.to_dict(sm_result), snapshot)
                                with state_lock:
                                    system_state["safe_mode_active"] = True
                                break
                    if safe_mode_triggered:
                        break

            # Update recovery counters for handled faults still in anomaly range
            for name, sub in subs.items():
                if sub["health"]["has_anomaly"]:
                    for ft in list(sub["recovery_counters"].keys()):
                        sub["recovery_counters"][ft] += 1

        except Exception as e:
            print(f"\n[ERROR] Tick {tick} exception (loop continues): {e}")
            import traceback
            traceback.print_exc()


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    from api import app

    # Start FDIR scenario loop in background thread
    scenario_thread = threading.Thread(target=run_fdir_scenario, daemon=True)
    scenario_thread.start()

    print(f"\n[GROUND STATION] API server starting...")
    print(f"[GROUND STATION] Endpoints:  http://localhost:{cfg.API_PORT}")
    print(f"[GROUND STATION] Docs:       http://localhost:{cfg.API_PORT}/docs")
    print(f"[GROUND STATION] Status:     http://localhost:{cfg.API_PORT}/status")
    print(f"[GROUND STATION] Events:     http://localhost:{cfg.API_PORT}/events\n")

    uvicorn.run(app, host="127.0.0.1", port=cfg.API_PORT, log_level="info")