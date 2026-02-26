"""
logger.py
=========
Structured event logging for the FDIR system.

Every event is logged with:
  - Timestamp, tick number, event type
  - Full justification / reasoning (§6.5 — no black-box logging)
  - System state snapshot at time of event (§9.1 Deliverable D4)
  - Mission phase and criticality included in ethical decision logs

Output:
  1. fdir_event_log.json — structured JSON for frontend/API consumption
  2. Colored terminal output — for live demo readability
"""

import json
import datetime
from pathlib import Path
from config import LOG_FILE


class EventType:
    SYSTEM_START      = "SYSTEM_START"
    SYSTEM_RESET      = "SYSTEM_RESET"
    SENSOR_DATA       = "SENSOR_DATA"
    TEMPORARY_ANOMALY = "TEMPORARY_ANOMALY"   # §5.2 distinct state
    ANOMALY_DETECTED  = "ANOMALY_DETECTED"
    FAULT_ISOLATED    = "FAULT_ISOLATED"
    ETHICAL_DECISION  = "ETHICAL_DECISION"
    RECOVERY_ACTION   = "RECOVERY_ACTION"
    HUMAN_ESCALATION  = "HUMAN_ESCALATION"
    HUMAN_APPROVAL    = "HUMAN_APPROVAL"      # when operator approves via API
    FAULT_INJECTED    = "FAULT_INJECTED"
    SAFE_MODE         = "SAFE_MODE"
    SYSTEM_NOMINAL    = "SYSTEM_NOMINAL"


class Color:
    RESET   = "\033[0m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    CYAN    = "\033[96m"
    MAGENTA = "\033[95m"
    BLUE    = "\033[94m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"


class FDIRLogger:

    def __init__(self):
        self.log_path  = Path(LOG_FILE)
        self.events    = []
        self.tick_count = 0
        self._initialize_log_file()

    def _initialize_log_file(self):
        self.log_path.write_text(json.dumps([], indent=2))

    def _timestamp(self) -> str:
        return datetime.datetime.utcnow().isoformat() + "Z"

    def _write_to_file(self):
        self.log_path.write_text(json.dumps(self.events, indent=2))

    def _add_event(self, event_type: str, data: dict, tick: int = None, state_snapshot: dict = None):
        """
        Core logging. Includes state_snapshot for §9.1 Deliverable D4.
        """
        event = {
            "timestamp":     self._timestamp(),
            "tick":          tick if tick is not None else self.tick_count,
            "event_type":    event_type,
            "data":          data,
            "state_snapshot": state_snapshot or {},
        }
        self.events.append(event)
        self._write_to_file()
        return event

    # ─────────────────────────────────────────────
    # PUBLIC LOGGING METHODS
    # ─────────────────────────────────────────────

    def log_system_start(self, mission_phase: str, subsystems: list = None):
        subs = subsystems or ["power"]
        subs_str = ", ".join(s.upper() for s in subs)
        print(f"\n{Color.BOLD}{Color.CYAN}{'='*65}{Color.RESET}")
        print(f"{Color.BOLD}{Color.CYAN}  FDIR SYSTEM — ONLINE{Color.RESET}")
        print(f"{Color.CYAN}  Subsystems: {subs_str}{Color.RESET}")
        print(f"{Color.CYAN}  Pipeline: Sensor→Monitor→Isolator→Ethics→Recovery{Color.RESET}")
        print(f"{Color.CYAN}  Mission Phase: {mission_phase}{Color.RESET}")
        print(f"{Color.CYAN}{'='*65}{Color.RESET}\n")
        self._add_event(EventType.SYSTEM_START, {
            "message":      "FDIR system initialized",
            "mission_phase": mission_phase,
            "subsystems":    subs,
        }, tick=0)

    def log_system_reset(self):
        print(f"\n{Color.CYAN}[RESET] System reset to nominal state{Color.RESET}\n")
        self._add_event(EventType.SYSTEM_RESET, {"message": "System reset"}, tick=0)

    def log_sensor_data(self, tick: int, all_sensor_data: dict):
        """Log sensor readings for all subsystems.

        Accepts either:
          - dict keyed by subsystem name (multi-subsystem mode)
          - flat dict with sensor keys (legacy single-subsystem mode)
        """
        self.tick_count = tick

        # Detect format: multi-subsystem has nested dicts
        if "power" in all_sensor_data or "thermal" in all_sensor_data:
            lines = []
            if "power" in all_sensor_data:
                d = all_sensor_data["power"]
                bk = f"  {Color.CYAN}[BACKUP]{Color.RESET}" if d.get("backup_active") else ""
                lines.append(
                    f"{Color.DIM}[T{tick:03d}]{Color.RESET} "
                    f"PWR  V:{d['voltage']:5.1f} | I:{d['current']:5.1f} | "
                    f"SoC:{d['soc']:5.1f} | T:{d['temperature']:5.1f}{bk}"
                )
            if "thermal" in all_sensor_data:
                d = all_sensor_data["thermal"]
                bk = f"  {Color.CYAN}[BKUP HTR]{Color.RESET}" if d.get("backup_heater_active") else ""
                lines.append(
                    f"       THRM Int:{d['internal_temp']:5.1f} | "
                    f"Rad:{d['radiator_temp']:5.1f} | "
                    f"Htr:{d['heater_power']:5.1f} | "
                    f"Pnl:{d['panel_temp']:5.1f}{bk}"
                )
            for line in lines:
                print(line)
        else:
            # Legacy single-subsystem format
            backup_tag = f"  {Color.CYAN}[BACKUP ACTIVE]{Color.RESET}" if all_sensor_data.get("backup_active") else ""
            print(
                f"{Color.DIM}[T{tick:03d}]{Color.RESET} "
                f"V:{all_sensor_data['voltage']:5.1f} | "
                f"I:{all_sensor_data['current']:5.1f} | "
                f"SoC:{all_sensor_data['soc']:5.1f} | "
                f"T:{all_sensor_data['temperature']:5.1f}"
                + backup_tag
            )
        self._add_event(EventType.SENSOR_DATA, all_sensor_data, tick=tick)

    def log_temporary_anomaly(self, tick: int, subsystem: str, health_report: dict):
        """§5.2: Log temporary anomaly as distinct state (not yet a confirmed fault)."""
        temp = health_report["temporary_anomalies"]
        tag = subsystem.upper()
        print(
            f"{Color.DIM}[T{tick:03d}] [{tag}] ~ TEMPORARY ANOMALY{Color.RESET} "
            f"→ {temp} | Monitoring... (not yet confirmed fault)"
        )
        self._add_event(EventType.TEMPORARY_ANOMALY, {
            "subsystem": subsystem,
            "temporary_anomalies": temp,
            "note": "Deviation detected but within noise/persistence window — not a confirmed fault",
        }, tick=tick)

    def log_anomaly(self, tick: int, subsystem: str, health_report: dict, state_snapshot: dict = None):
        anomalies = health_report["confirmed_anomalies"]
        tag = subsystem.upper()
        print(
            f"\n{Color.YELLOW}[T{tick:03d}] [{tag}] \u26a0  ANOMALY CONFIRMED{Color.RESET} "
            f"→ Parameters: {anomalies} | Status: {health_report['overall_status']}"
        )
        self._add_event(EventType.ANOMALY_DETECTED, {
            "subsystem":           subsystem,
            "confirmed_anomalies": anomalies,
            "overall_status":      health_report["overall_status"],
            "parameters":          {k: v["status"] for k, v in health_report["parameters"].items()},
        }, tick=tick, state_snapshot=state_snapshot)

    def log_fault_isolation(self, tick: int, subsystem: str, diagnosis_dict: dict, state_snapshot: dict = None):
        tag = subsystem.upper()
        print(
            f"{Color.RED}[T{tick:03d}] [{tag}] \U0001f50d FAULT ISOLATED{Color.RESET}"
            f" → {diagnosis_dict['fault_type'].upper()} | "
            f"Confidence: {diagnosis_dict['confidence_pct']} | "
            f"Risk: {diagnosis_dict['risk_level']} | "
            f"Reversibility: {diagnosis_dict['reversibility']}"
        )
        print(f"         Reasoning: {diagnosis_dict['isolation_reasoning']}")
        self._add_event(EventType.FAULT_ISOLATED, diagnosis_dict, tick=tick, state_snapshot=state_snapshot)

    def log_ethical_decision(self, tick: int, ethical_dict: dict, state_snapshot: dict = None):
        level = ethical_dict["autonomy_level"]
        color = {
            "FULL_AUTONOMOUS":  Color.GREEN,
            "LIMITED_ACTION":   Color.YELLOW,
            "HUMAN_ESCALATION": Color.RED,
        }.get(level, Color.RESET)
        print(
            f"{color}[T{tick:03d}] ⚖  ETHICAL DECISION: {level}{Color.RESET}"
            f" → Action: {ethical_dict['permitted_action']}"
            f" | Mission: {ethical_dict['mission_phase']} ({ethical_dict['mission_criticality']})"
        )
        print(f"         {ethical_dict['reasoning']}")
        self._add_event(EventType.ETHICAL_DECISION, ethical_dict, tick=tick, state_snapshot=state_snapshot)

    def log_recovery(self, tick: int, subsystem: str, recovery_dict: dict, state_snapshot: dict = None):
        tag = subsystem.upper()
        print(
            f"{Color.GREEN}[T{tick:03d}] [{tag}] \u2705 RECOVERY EXECUTED{Color.RESET}"
            f" \u2192 {recovery_dict['action_taken']} | {recovery_dict['description']}"
        )
        if recovery_dict["side_effects"]:
            print(f"         Side effects: {' | '.join(recovery_dict['side_effects'])}")
        recovery_dict_with_sub = {**recovery_dict, "subsystem": subsystem}
        self._add_event(EventType.RECOVERY_ACTION, recovery_dict_with_sub, tick=tick, state_snapshot=state_snapshot)

    def log_human_escalation(self, tick: int, message: str, state_snapshot: dict = None):
        print(f"\n{Color.MAGENTA}[T{tick:03d}] 🚨 HUMAN ESCALATION — AUTONOMOUS ACTION BLOCKED{Color.RESET}")
        print(f"         {message}")
        self._add_event(EventType.HUMAN_ESCALATION, {"message": message}, tick=tick, state_snapshot=state_snapshot)

    def log_human_approval(self, tick: int, fault_type: str, approved_action: str):
        print(f"\n{Color.GREEN}[T{tick:03d}] 👤 HUMAN APPROVAL RECEIVED{Color.RESET} → {fault_type}: {approved_action}")
        self._add_event(EventType.HUMAN_APPROVAL, {
            "fault_type":      fault_type,
            "approved_action": approved_action,
        }, tick=tick)

    def log_fault_injected(self, tick: int, subsystem: str, fault_config: dict):
        tag = subsystem.upper()
        line = '\u2500' * 60
        print(f"\n{Color.RED}{line}{Color.RESET}")
        print(f"{Color.RED}[T{tick:03d}] [{tag}] \U0001f4a5 FAULT INJECTED: {fault_config['type'].upper()}{Color.RESET}")
        print(f"         {fault_config['description']}")
        print(f"{Color.RED}{line}{Color.RESET}")
        self._add_event(EventType.FAULT_INJECTED, {**fault_config, "subsystem": subsystem}, tick=tick)

    def log_recovery_in_progress(self, tick: int, subsystem: str, fault_type: str):
        """Printed once after recovery while sensor values are still catching up."""
        tag = subsystem.upper()
        print(f"{Color.DIM}[T{tick:03d}] [{tag}] \u21bb Recovery in progress for '{fault_type}' \u2014 sensor values returning to nominal{Color.RESET}")

    def log_safe_mode(self, tick: int, reason: str):
        print(f"\n{Color.RED}[T{tick:03d}] 🛡  SAFE MODE ENGAGED — {reason}{Color.RESET}")
        self._add_event(EventType.SAFE_MODE, {"reason": reason}, tick=tick)

    def log_system_nominal(self, tick: int):
        print(f"{Color.GREEN}[T{tick:03d}] ✓ System nominal — all parameters within bounds{Color.RESET}")
        self._add_event(EventType.SYSTEM_NOMINAL, {"message": "All parameters nominal"}, tick=tick)

    def get_recent_events(self, n: int = 50) -> list:
        return self.events[-n:]

    def get_all_events(self) -> list:
        return self.events

    def clear(self):
        self.events = []
        self._initialize_log_file()