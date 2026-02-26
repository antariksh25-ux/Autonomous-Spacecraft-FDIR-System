"""
fault_isolator.py
=================
Receives confirmed anomalies from the Health Monitor.
Identifies the ROOT CAUSE by cross-checking sensor patterns against known fault signatures.
Computes a CONFIDENCE SCORE (0.0–1.0) that drives the Ethical Engine's decision.

Architecture: Health Monitor → [Fault Isolator] → Ethical Engine
"""

from dataclasses import dataclass
from typing import Optional
from health_monitor import HealthStatus


@dataclass
class FaultDiagnosis:
    fault_type:          str
    affected_params:     list
    confidence:          float
    risk_level:          str     # "LOW" | "MEDIUM" | "HIGH"
    reversibility:       str     # "HIGH" | "MEDIUM" | "LOW"
    description:         str
    recommended_action:  str
    isolation_reasoning: str


# ─────────────────────────────────────────────
# FAULT SIGNATURE LIBRARY
# Defines expected sensor patterns for each fault type.
# Cross-matching actual anomalies against signatures → confidence score.
# ─────────────────────────────────────────────
FAULT_SIGNATURES = {
    "voltage_drop": {
        "primary_param":   "voltage",
        "corroborating":   ["soc"],        # low voltage correlates with SoC drop
        "contradicting":   [],
        "risk_level":      "LOW",
        "reversibility":   "HIGH",
        "description":     "Primary power regulator voltage drop — likely regulator degradation or partial failure",
        "recovery_action": "switch_to_backup_regulator",
        "base_confidence": 0.78,  # raised: LOW risk fault should reach FULL_AUTONOMOUS threshold
    },
    "overcurrent": {
        "primary_param":   "current",
        "corroborating":   ["temperature"],  # high current → heat buildup
        "contradicting":   [],
        "risk_level":      "MEDIUM",
        "reversibility":   "HIGH",
        "description":     "Overcurrent condition — excess load on primary bus or short circuit",
        "recovery_action": "reduce_load",
        "base_confidence": 0.65,
    },
    "battery_drain": {
        "primary_param":   "soc",
        "corroborating":   ["voltage"],    # battery drain causes voltage sag
        "contradicting":   [],
        "risk_level":      "HIGH",
        "reversibility":   "MEDIUM",
        "description":     "Abnormal battery depletion — possible charge controller failure or excessive load",
        "recovery_action": "emergency_charge",
        "base_confidence": 0.55,
    },
    "thermal_overload": {
        "primary_param":   "temperature",
        "corroborating":   ["current"],    # thermal overload follows high current
        "contradicting":   [],
        "risk_level":      "HIGH",
        "reversibility":   "MEDIUM",
        "description":     "Regulator thermal overload — risk of permanent hardware damage if unaddressed",
        "recovery_action": "thermal_throttle",
        "base_confidence": 0.70,
    },
}


class FaultIsolator:

    def __init__(self):
        self.last_diagnosis: Optional[FaultDiagnosis] = None

    def _compute_confidence(
        self, signature: dict, confirmed_anomalies: list, parameter_reports: dict
    ) -> tuple:
        """
        Confidence scoring:
          base_confidence          — starting point from signature library
          +0.15 per corroborating sensor also anomalous
          -0.20 per contradicting sensor anomalous (unexpected pattern)
          +0.10 if primary parameter is CRITICAL severity (not just WARNING)
        Returns (confidence: float, reasoning: str)
        """
        confidence = signature["base_confidence"]
        parts = [
            f"Primary '{signature['primary_param']}' anomaly confirmed "
            f"(base confidence: {signature['base_confidence']:.0%})"
        ]

        for param in signature["corroborating"]:
            if param in confirmed_anomalies:
                confidence += 0.15
                parts.append(f"Corroborating: '{param}' also anomalous (+15%)")

        for param in signature.get("contradicting", []):
            if param in confirmed_anomalies:
                confidence -= 0.20
                parts.append(f"Contradicting: '{param}' anomalous unexpectedly (-20%)")

        primary = signature["primary_param"]
        if primary in parameter_reports:
            if parameter_reports[primary]["status"] == HealthStatus.CRITICAL:
                confidence += 0.10
                parts.append("Primary parameter at CRITICAL severity (+10%)")

        confidence = round(max(0.0, min(1.0, confidence)), 3)
        return confidence, " | ".join(parts)

    def isolate(self, health_report: dict) -> Optional[FaultDiagnosis]:
        """
        Match confirmed anomaly pattern against fault signatures.
        Returns the highest-confidence FaultDiagnosis, or None if unrecognized.
        """
        confirmed_anomalies = health_report["confirmed_anomalies"]
        parameter_reports   = health_report["parameters"]

        if not confirmed_anomalies:
            return None

        candidates = []
        for fault_type, signature in FAULT_SIGNATURES.items():
            if signature["primary_param"] not in confirmed_anomalies:
                continue
            confidence, reasoning = self._compute_confidence(
                signature, confirmed_anomalies, parameter_reports
            )
            candidates.append((fault_type, confidence, reasoning, signature))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1], reverse=True)
        best_type, best_confidence, best_reasoning, best_sig = candidates[0]

        diagnosis = FaultDiagnosis(
            fault_type          = best_type,
            affected_params     = confirmed_anomalies,
            confidence          = best_confidence,
            risk_level          = best_sig["risk_level"],
            reversibility       = best_sig["reversibility"],
            description         = best_sig["description"],
            recommended_action  = best_sig["recovery_action"],
            isolation_reasoning = best_reasoning,
        )
        self.last_diagnosis = diagnosis
        return diagnosis

    def to_dict(self, diagnosis: FaultDiagnosis) -> dict:
        return {
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