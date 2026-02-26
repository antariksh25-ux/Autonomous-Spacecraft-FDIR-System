from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import FDIRConfig, channel_index
from .db import SqliteRepo
from .layers.anomaly_detection import AnomalyDetection
from .layers.ethical_constraints import EthicalAutonomyConstraintLayer
from .layers.fault_isolation import FaultIsolation
from .layers.health_monitoring import HealthMonitoring
from .layers.recovery_engine import RecoveryEngine
from .log_buffer import LogBuffer
from .store import TelemetryStore
from .types import AutonomyDecisionLevel, FaultRecord, RiskLevel, SystemMode, TelemetrySample


def _risk_rank(r: RiskLevel) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(r.value, 0)


class FDIRSystem:
    def __init__(self, config: FDIRConfig, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.config = config
        self._idx = channel_index(config.channels)
        self._logs = LogBuffer(capacity=4000)
        self._telemetry = TelemetryStore(config.channels)

        self._health = HealthMonitoring(config.channels)
        self._detector = AnomalyDetection(
            config.channels,
            persistence_samples=config.persistence_samples,
            cross_sensor_min=config.cross_sensor_min,
        )
        self._isolation = FaultIsolation(config.channels)
        self._ethics = EthicalAutonomyConstraintLayer(config.mission_phase)
        self._recovery = RecoveryEngine(max_attempts=3)

        self._repo = SqliteRepo(data_dir / "fdir.db")
        self.mode = SystemMode.run
        self._active_fault: Optional[FaultRecord] = None
        self._last_persisted_log_seq = 0

        self._logs.add("info", "system", "FDIR system initialized", {"channels": len(config.channels)})

    @property
    def log_seq(self) -> int:
        return self._logs.seq

    def add_log(self, level: str, stage: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        self._logs.add(level, stage, message, details or {})
        self._persist_new_logs()

    def ingest(self, sample: TelemetrySample) -> Dict[str, Any]:
        if self.mode == SystemMode.hold:
            self._logs.add("warning", "ingest", "System in HOLD; telemetry ingested but actions suppressed")

        self._telemetry.ingest(sample)
        self._repo.insert_telemetry(sample.timestamp_iso, self._telemetry.latest_values())

        telemetry = self._telemetry.latest_values()
        confirmed = self._detector.update(telemetry)
        isolations = self._isolation.isolate(telemetry, confirmed)

        if isolations:
            top = sorted(isolations, key=lambda r: (r.confidence), reverse=True)[0]
            spec_risks = [self._idx[c].risk for c in confirmed.get(top.subsystem, []) if c in self._idx]
            risk = max(spec_risks, default=RiskLevel.low, key=_risk_rank)
            reversible = True

            ethical = self._ethics.decide(confidence=top.confidence, risk=risk, reversible=reversible)
            escalated = ethical.level == AutonomyDecisionLevel.human_escalation

            action = None
            if not escalated and self.mode == SystemMode.run:
                action = self._recovery.propose(top.subsystem, top.fault_type)

            fault_id = str(uuid.uuid4())
            active_fault = FaultRecord(
                fault_id=fault_id,
                timestamp_iso=datetime.now(timezone.utc).isoformat(),
                subsystem=top.subsystem,
                component=top.component,
                fault_type=top.fault_type,
                severity=top.severity,
                confidence=float(top.confidence),
                ethical_level=ethical.level,
                ethical_justification=ethical.justification,
                action_taken=action.action if action else None,
                action_rationale=action.rationale if action else None,
                escalated=escalated,
            )

            self._active_fault = active_fault
            self._repo.upsert_fault(
                {
                    **asdict(active_fault),
                    "severity": active_fault.severity.value,
                    "ethical_level": active_fault.ethical_level.value,
                }
            )

            self._logs.add(
                "warning" if escalated else "info",
                "fault",
                f"Fault isolated: {top.subsystem}/{top.component} ({top.fault_type})",
                {
                    "confidence": top.confidence,
                    "ethical": ethical.level.value,
                    "risk": ethical.risk.value,
                    "action": action.action if action else None,
                },
            )
            if escalated:
                self.mode = SystemMode.hold
                self._logs.add("error", "ethics", "Entered HOLD awaiting human decision")

        self._persist_new_logs()
        return self.snapshot(include_logs=True, logs_limit=120)

    def _persist_new_logs(self) -> None:
        new_entries = self._logs.since(self._last_persisted_log_seq)
        if not new_entries:
            return
        for e in new_entries:
            self._repo.insert_log(
                seq=e.seq,
                timestamp_iso=e.timestamp_iso,
                level=e.level,
                stage=e.stage,
                message=e.message,
                details_json=json.dumps(e.details, separators=(",", ":")),
            )
        self._last_persisted_log_seq = new_entries[-1].seq

    def reset(self) -> Dict[str, Any]:
        self.mode = SystemMode.run
        self._active_fault = None
        self._logs.add("info", "control", "System reset")
        self._persist_new_logs()
        return {"ok": True}

    def snapshot(self, include_logs: bool, logs_limit: int = 120) -> Dict[str, Any]:
        telemetry = self._telemetry.latest_values()
        health = self._health.evaluate(telemetry)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": self.mode.value,
            "mission_phase": self.config.mission_phase,
            "telemetry": telemetry,
            "health": [
                {
                    **asdict(h),
                    "severity": h.severity.value,
                    "sensors": [
                        {
                            **asdict(s),
                        }
                        for s in h.sensors
                    ],
                }
                for h in health
            ],
            "active_fault": (
                {
                    **asdict(self._active_fault),
                    "severity": self._active_fault.severity.value,
                    "ethical_level": self._active_fault.ethical_level.value,
                }
                if self._active_fault
                else None
            ),
            "recovery_action": None,
            "fault_count": 1 if self._active_fault else 0,
            "log_seq": self._logs.seq,
            "logs": [asdict(e) for e in self._logs.tail(logs_limit)] if include_logs else [],
            "telemetry_state": {
                "last_rx_iso": self._telemetry.state.last_rx_iso,
                "total_samples": self._telemetry.state.total_samples,
            },
        }

    def list_faults(self, limit: int = 50) -> Dict[str, Any]:
        return {"faults": self._repo.list_faults(limit=limit)}

    def list_logs(self, since_seq: int = 0, limit: int = 200) -> Dict[str, Any]:
        rows = self._repo.list_logs(since_seq=since_seq, limit=limit)
        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            raw = d.pop("details_json", "{}")
            try:
                d["details"] = json.loads(raw) if raw else {}
            except Exception:
                d["details"] = {"_raw": raw}
            out.append(d)
        return {"logs": out}
