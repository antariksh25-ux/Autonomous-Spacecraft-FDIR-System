"""
subsystems/base.py
==================
Shared data structures and generic components for all FDIR subsystems.

Architecture:
  Each subsystem provides a SIMULATOR (physics model) and FAULT SIGNATURES.
  The generic SubsystemMonitor and SubsystemIsolator handle detection and
  isolation for ANY subsystem using configuration-driven logic.

  This keeps subsystem-specific code minimal: just the simulator and signatures.
"""

from collections import deque
from dataclasses import dataclass
from typing import Optional


# ─────────────────────────────────────────────
# SHARED TYPES
# ─────────────────────────────────────────────

class HealthStatus:
    """Three-state health classification per §5.2."""
    NOMINAL           = "NOMINAL"
    TEMPORARY_ANOMALY = "TEMPORARY_ANOMALY"
    WARNING           = "WARNING"
    CRITICAL          = "CRITICAL"


@dataclass
class FaultDiagnosis:
    """Unified fault diagnosis — the contract between Isolation → Ethics → Recovery.

    Every subsystem's isolator produces this same structure.
    The Ethical Engine and Recovery Module depend ONLY on this dataclass,
    making them fully subsystem-agnostic.
    """
    subsystem:           str    # "power" | "thermal" | ...
    fault_type:          str
    affected_params:     list
    confidence:          float
    risk_level:          str    # "LOW" | "MEDIUM" | "HIGH"
    reversibility:       str    # "HIGH" | "MEDIUM" | "LOW"
    description:         str
    recommended_action:  str
    isolation_reasoning: str


# ─────────────────────────────────────────────
# PARAMETER MONITOR (generic, reusable)
# ─────────────────────────────────────────────

class ParameterMonitor:
    """Single-parameter health monitor with three-state classification
    and a noise-aware persistence filter (§5.2).

    Reusable by any subsystem — configurable direction, thresholds, noise band.

    Args:
        name:               parameter name (e.g. "voltage", "internal_temp")
        thresholds:         dict with "warning" and "critical" keys
        nominal:            dict with "min", "max", "nominal" keys
        direction:          "upper" (fault = value too high) or "lower" (fault = value too low)
        persistence_window: consecutive anomalous ticks to confirm fault
        noise_band:         tolerance around warning threshold
    """

    def __init__(self, name: str, thresholds: dict, nominal: dict,
                 direction: str, persistence_window: int, noise_band: float):
        self.name = name
        self.thresholds = thresholds
        self.nominal = nominal
        self.direction = direction
        self.persistence_window = persistence_window
        self.noise_band = noise_band
        self.history: deque = deque(maxlen=persistence_window)
        self.status = HealthStatus.NOMINAL
        self.anomaly_confirmed = False

    def _raw_classify(self, value: float) -> str:
        t = self.thresholds
        if self.direction == "upper":
            if value >= t["critical"]:
                return HealthStatus.CRITICAL
            elif value >= t["warning"]:
                return HealthStatus.WARNING
            return HealthStatus.NOMINAL
        else:  # lower
            if value <= t["critical"]:
                return HealthStatus.CRITICAL
            elif value <= t["warning"]:
                return HealthStatus.WARNING
            return HealthStatus.NOMINAL

    def _is_near_noise_band(self, value: float) -> bool:
        return abs(value - self.thresholds["warning"]) <= self.noise_band

    def update(self, value: float) -> dict:
        raw_class = self._raw_classify(value)
        near_noise = self._is_near_noise_band(value)
        self.history.append(raw_class)

        window_full = len(self.history) == self.persistence_window
        non_nominal = [s for s in self.history if s != HealthStatus.NOMINAL]

        if raw_class == HealthStatus.NOMINAL:
            self.status = HealthStatus.NOMINAL
            self.anomaly_confirmed = False
        elif not window_full:
            self.status = HealthStatus.TEMPORARY_ANOMALY
            self.anomaly_confirmed = False
        elif near_noise and len(non_nominal) < self.persistence_window:
            self.status = HealthStatus.TEMPORARY_ANOMALY
            self.anomaly_confirmed = False
        elif len(non_nominal) == self.persistence_window:
            self.anomaly_confirmed = True
            self.status = (HealthStatus.CRITICAL
                           if HealthStatus.CRITICAL in self.history
                           else HealthStatus.WARNING)
        else:
            self.status = HealthStatus.TEMPORARY_ANOMALY
            self.anomaly_confirmed = False

        return {
            "parameter":         self.name,
            "value":             value,
            "status":            self.status,
            "anomaly_confirmed": self.anomaly_confirmed,
            "near_noise_band":   near_noise,
            "window":            list(self.history),
        }

    def reset(self):
        self.history.clear()
        self.status = HealthStatus.NOMINAL
        self.anomaly_confirmed = False


# ─────────────────────────────────────────────
# SUBSYSTEM MONITOR (generic, config-driven)
# ─────────────────────────────────────────────

class SubsystemMonitor:
    """Health monitor for any subsystem.  Aggregates ParameterMonitors.

    §5.1: Continuous monitoring.
    §5.7: Resource-aware — simple comparisons only, no ML.
    """

    def __init__(self, subsystem_name: str, nominal: dict, thresholds: dict,
                 directions: dict, persistence_window: int, noise_band: float):
        self.subsystem = subsystem_name
        self.monitors = {
            param: ParameterMonitor(
                name=param,
                thresholds=thresholds[param],
                nominal=nominal[param],
                direction=directions[param],
                persistence_window=persistence_window,
                noise_band=noise_band,
            )
            for param in nominal
        }
        self.tick_count = 0

    def process(self, sensor_data: dict) -> dict:
        """Process one tick of sensor data.  Returns unified health report."""
        self.tick_count += 1
        parameter_reports   = {}
        confirmed_anomalies = []
        temporary_anomalies = []

        for param, monitor in self.monitors.items():
            if param in sensor_data:
                report = monitor.update(sensor_data[param])
                parameter_reports[param] = report
                if report["anomaly_confirmed"]:
                    confirmed_anomalies.append(param)
                elif report["status"] == HealthStatus.TEMPORARY_ANOMALY:
                    temporary_anomalies.append(param)

        all_statuses = [r["status"] for r in parameter_reports.values()]
        if HealthStatus.CRITICAL in all_statuses:
            overall = HealthStatus.CRITICAL
        elif HealthStatus.WARNING in all_statuses:
            overall = HealthStatus.WARNING
        elif HealthStatus.TEMPORARY_ANOMALY in all_statuses:
            overall = HealthStatus.TEMPORARY_ANOMALY
        else:
            overall = HealthStatus.NOMINAL

        return {
            "tick":                self.tick_count,
            "subsystem":           self.subsystem,
            "overall_status":      overall,
            "confirmed_anomalies": confirmed_anomalies,
            "temporary_anomalies": temporary_anomalies,
            "has_anomaly":         len(confirmed_anomalies) > 0,
            "has_temporary":       len(temporary_anomalies) > 0,
            "parameters":          parameter_reports,
        }

    def reset_parameter(self, param: str):
        if param in self.monitors:
            self.monitors[param].reset()

    def reset_all(self):
        for m in self.monitors.values():
            m.reset()
        self.tick_count = 0


# ─────────────────────────────────────────────
# SUBSYSTEM ISOLATOR (generic, signature-driven)
# ─────────────────────────────────────────────

class SubsystemIsolator:
    """Fault isolation for any subsystem using signature matching.

    Receives confirmed anomalies from a SubsystemMonitor.
    Cross-checks against a fault signature library to identify root cause.
    Computes confidence score that drives the Ethical Engine's decision.
    """

    def __init__(self, subsystem_name: str, fault_signatures: dict):
        self.subsystem = subsystem_name
        self.signatures = fault_signatures
        self.last_diagnosis: Optional[FaultDiagnosis] = None

    def _compute_confidence(self, signature: dict, confirmed: list,
                            parameter_reports: dict) -> tuple:
        """
        Confidence scoring:
          base_confidence          — starting point from signature library
          +0.15 per corroborating sensor also anomalous
          -0.20 per contradicting sensor anomalous (unexpected pattern)
          +0.10 if primary parameter is CRITICAL severity
        """
        confidence = signature["base_confidence"]
        parts = [
            f"[{self.subsystem.upper()}] Primary '{signature['primary_param']}' "
            f"anomaly confirmed (base: {signature['base_confidence']:.0%})"
        ]

        for p in signature.get("corroborating", []):
            if p in confirmed:
                confidence += 0.15
                parts.append(f"Corroborating: '{p}' also anomalous (+15%)")

        for p in signature.get("contradicting", []):
            if p in confirmed:
                confidence -= 0.20
                parts.append(f"Contradicting: '{p}' anomalous unexpectedly (-20%)")

        primary = signature["primary_param"]
        if primary in parameter_reports:
            if parameter_reports[primary]["status"] == HealthStatus.CRITICAL:
                confidence += 0.10
                parts.append("Primary at CRITICAL severity (+10%)")

        confidence = round(max(0.0, min(1.0, confidence)), 3)
        return confidence, " | ".join(parts)

    def isolate(self, health_report: dict) -> Optional[FaultDiagnosis]:
        """Match confirmed anomaly pattern against fault signatures.
        Returns highest-confidence FaultDiagnosis, or None if unrecognized."""
        all_diags = self.isolate_all(health_report)
        if not all_diags:
            return None
        self.last_diagnosis = all_diags[0]
        return all_diags[0]

    def isolate_all(self, health_report: dict) -> list:
        """Returns ALL matching fault diagnoses sorted by confidence (highest first).
        Used when multiple faults may be active simultaneously."""
        confirmed = health_report["confirmed_anomalies"]
        params    = health_report["parameters"]

        if not confirmed:
            return []

        candidates = []
        for fault_type, sig in self.signatures.items():
            if sig["primary_param"] not in confirmed:
                continue
            conf, reasoning = self._compute_confidence(sig, confirmed, params)
            candidates.append((fault_type, conf, reasoning, sig))

        if not candidates:
            return []

        candidates.sort(key=lambda x: x[1], reverse=True)

        diagnoses = []
        for fault_type, conf, reasoning, sig in candidates:
            diagnoses.append(FaultDiagnosis(
                subsystem           = self.subsystem,
                fault_type          = fault_type,
                affected_params     = confirmed,
                confidence          = conf,
                risk_level          = sig["risk_level"],
                reversibility       = sig["reversibility"],
                description         = sig["description"],
                recommended_action  = sig["recovery_action"],
                isolation_reasoning = reasoning,
            ))
        return diagnoses

    @staticmethod
    def to_dict(diagnosis: FaultDiagnosis) -> dict:
        return {
            "subsystem":           diagnosis.subsystem,
            "fault_type":          diagnosis.fault_type,
            "affected_params":     diagnosis.affected_params,
            "confidence":          diagnosis.confidence,
            "confidence_pct":      f"{diagnosis.confidence:.0%}",
            "risk_level":          diagnosis.risk_level,
            "reversibility":       diagnosis.reversibility,
            "description":         diagnosis.description,
            "recommended_action":  diagnosis.recommended_action,
            "isolation_reasoning": diagnosis.isolation_reasoning,
        }

    def reset(self):
        self.last_diagnosis = None