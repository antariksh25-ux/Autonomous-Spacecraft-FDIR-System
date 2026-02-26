from __future__ import annotations

from ..types import AutonomyDecisionLevel, EthicalDecision, RiskLevel


class EthicalAutonomyConstraintLayer:
    def __init__(self, mission_phase: str):
        self._mission_phase = mission_phase

    def decide(self, confidence: float, risk: RiskLevel, reversible: bool) -> EthicalDecision:
        mission_critical = self._mission_phase.lower() in {"launch", "critical_maneuver", "insertion"}

        if mission_critical:
            return EthicalDecision(
                level=AutonomyDecisionLevel.human_escalation,
                justification=f"Mission phase '{self._mission_phase}' requires human approval",
                risk=risk,
            )

        if confidence <= 0.5:
            return EthicalDecision(
                level=AutonomyDecisionLevel.human_escalation,
                justification="Low diagnostic confidence; escalate to human",
                risk=risk,
            )

        if not reversible:
            return EthicalDecision(
                level=AutonomyDecisionLevel.human_escalation,
                justification="Proposed action not reversible; escalate to human",
                risk=risk,
            )

        if confidence > 0.8 and risk == RiskLevel.low:
            return EthicalDecision(
                level=AutonomyDecisionLevel.full_autonomy,
                justification="High confidence, low risk, reversible action",
                risk=risk,
            )

        if confidence > 0.5:
            return EthicalDecision(
                level=AutonomyDecisionLevel.limited_autonomy,
                justification="Moderate confidence or elevated risk; limit autonomy",
                risk=risk,
            )

        return EthicalDecision(level=AutonomyDecisionLevel.monitor, justification="Monitoring", risk=risk)
