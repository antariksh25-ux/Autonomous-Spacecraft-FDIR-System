"""
ethical_engine.py
=================
THE ETHICAL AUTONOMY CONSTRAINT LAYER — §6 compliance

Governs WHEN and HOW autonomous action is permitted.
No recovery action bypasses this engine.

Decision inputs (§6.1):
  - Diagnostic confidence   (from Fault Isolator)
  - Risk level              (from fault signature)
  - Action reversibility    (from fault signature)
  - Mission criticality     (from config MISSION_PHASE — §6.1 requirement)

Decision outcomes (§6.3 table):
  ┌─────────────────────────────────────────┬──────────────────────────────────┐
  │ Condition                               │ Outcome                          │
  ├─────────────────────────────────────────┼──────────────────────────────────┤
  │ High confidence + Low risk              │ FULL_AUTONOMOUS recovery          │
  │ High confidence + Med risk + reversible │ LIMITED_ACTION (safe fallback)    │
  │ High confidence + High risk             │ HUMAN_ESCALATION (explicit appr.) │
  │ Medium confidence                       │ LIMITED_ACTION                    │
  │ Low confidence OR irreversible action   │ HUMAN_ESCALATION                  │
  │ CRITICAL_MANEUVER mission phase         │ HUMAN_ESCALATION (always)         │
  └─────────────────────────────────────────┴──────────────────────────────────┘

§6.4 Human Accountability:
  When HUMAN_ESCALATION is issued, a human_hold flag is set.
  No further autonomous action on this fault until human clears it via API.

§6.5 Transparency:
  Every decision includes a full 'reasoning' string explaining:
  - Why this autonomy level was chosen
  - What inputs drove the decision
  - What the permitted action is and why
"""

from dataclasses import dataclass
from subsystems.base import FaultDiagnosis
import config as _cfg   # import module (not values) so mission phase is read dynamically each call

ETHICAL = _cfg.ETHICAL


class AutonomyDecision:
    FULL_AUTONOMOUS  = "FULL_AUTONOMOUS"
    LIMITED_ACTION   = "LIMITED_ACTION"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"


RISK_SCORE         = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
REVERSIBILITY_SCORE = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

# Fallback (safe) actions for when full recommended action is not authorized
LIMITED_ACTION_MAP = {
    # Power subsystem
    "voltage_drop":        "reduce_load",
    "overcurrent":         "reduce_load",
    "battery_drain":       "reduce_load",
    "thermal_overload":    "thermal_throttle",
    # Thermal subsystem
    "thermal_runaway":     "reduce_load",
    "heater_failure":      "reduce_load",
    "radiator_degradation": "reduce_load",
}


@dataclass
class EthicalDecisionResult:
    subsystem:           str    # source subsystem (pass-through from diagnosis)
    autonomy_level:      str
    permitted_action:    str
    confidence:          float
    risk_level:          str
    reversibility:       str
    mission_criticality: str    # §6.1 — included in every decision
    mission_phase:       str
    reasoning:           str    # §6.5 — full explanation
    human_message:       str    # operator-facing message when escalating
    requires_human_hold: bool   # §6.4 — blocks further autonomous action


class EthicalEngine:
    """
    Implements §6.1–6.5 Ethical Autonomy Constraint Layer.
    Fully deterministic — no black-box behavior.
    """

    def __init__(self):
        self.decision_history = []
        # §6.4: Track faults under human hold — autonomous action blocked
        self.human_hold_faults: set = set()

    def is_under_human_hold(self, fault_type: str) -> bool:
        """Returns True if this fault type is currently held pending human approval."""
        return fault_type in self.human_hold_faults

    def clear_human_hold(self, fault_type: str):
        """Called by human approval API endpoint to release hold."""
        self.human_hold_faults.discard(fault_type)

    def clear_all_holds(self):
        """Used on system reset."""
        self.human_hold_faults.clear()

    def evaluate(self, diagnosis: FaultDiagnosis) -> EthicalDecisionResult:
        """
        Core ethical evaluation.
        Returns a fully reasoned EthicalDecisionResult.
        """
        confidence       = diagnosis.confidence
        risk_level       = diagnosis.risk_level
        reversibility    = diagnosis.reversibility
        fault_type       = diagnosis.fault_type
        recommended      = diagnosis.recommended_action

        risk_score       = RISK_SCORE[risk_level]
        rev_score        = REVERSIBILITY_SCORE[reversibility]

        # Get current mission phase and criticality (§6.1)
        # Read from module directly so live changes via /mission-phase API take effect
        current_phase       = _cfg.MISSION_PHASE
        mission_criticality = _cfg.MISSION_PHASE_CRITICALITY.get(current_phase, "LOW")
        mission_crit_score  = RISK_SCORE.get(mission_criticality, 1)

        # ─────────────────────────────────────────────────────────
        # DECISION TREE — fully documented per §6.3 and §6.4
        # ─────────────────────────────────────────────────────────

        # OVERRIDE: CRITICAL mission phase → always escalate (§5.6, §6.4)
        if mission_crit_score == 3:
            autonomy_level   = AutonomyDecision.HUMAN_ESCALATION
            permitted_action = "none"
            self.human_hold_faults.add(fault_type)
            reasoning = (
                f"HUMAN ESCALATION REQUIRED — MISSION PHASE OVERRIDE. "
                f"Current mission phase is '{current_phase}' (criticality: {mission_criticality}). "
                f"§5.6 requires human-in-the-loop during mission-critical phases. "
                f"Autonomous action is prohibited regardless of fault confidence ({confidence:.0%}). "
                f"Human operator must authorize all recovery actions during this phase."
            )
            human_message = (
                f"OPERATOR ACTION REQUIRED. Mission phase '{current_phase}' prohibits autonomous recovery. "
                f"Fault: {fault_type} | Confidence: {confidence:.0%} | Risk: {risk_level}. "
                f"Awaiting your authorization."
            )

        # CASE 1: Low confidence → Escalate regardless (§6.2, §6.3)
        elif confidence < ETHICAL["confidence_medium"]:
            autonomy_level   = AutonomyDecision.HUMAN_ESCALATION
            permitted_action = "none"
            self.human_hold_faults.add(fault_type)
            reasoning = (
                f"HUMAN ESCALATION REQUIRED — LOW CONFIDENCE. "
                f"Confidence ({confidence:.0%}) is below minimum threshold "
                f"({ETHICAL['confidence_medium']:.0%}). "
                f"§6.2: Autonomous action is not justified — the risk of incorrect recovery "
                f"on an uncertain diagnosis outweighs the risk of inaction. "
                f"System holds current state. No autonomous action taken."
            )
            human_message = (
                f"OPERATOR ACTION REQUIRED. Fault suspected: {fault_type}. "
                f"Confidence {confidence:.0%} is too low for autonomous action. "
                f"Affected parameters: {diagnosis.affected_params}. "
                f"System stable — awaiting your decision."
            )

        # CASE 2: High confidence + Low risk → Full autonomy (§6.3 row 1)
        elif confidence >= ETHICAL["confidence_high"] and risk_score == 1:
            autonomy_level   = AutonomyDecision.FULL_AUTONOMOUS
            permitted_action = recommended
            reasoning = (
                f"FULL AUTONOMOUS RECOVERY AUTHORIZED. "
                f"Confidence ({confidence:.0%}) ≥ high threshold ({ETHICAL['confidence_high']:.0%}). "
                f"Risk level: {risk_level} (score: {risk_score}/3) — low risk action. "
                f"Reversibility: {reversibility} — action is undoable if needed. "
                f"Mission phase '{current_phase}' (criticality: {mission_criticality}) — "
                f"autonomy permitted in this phase. "
                f"All §6.1 constraints satisfied. Action '{recommended}' authorized for immediate execution."
            )
            human_message = ""

        # CASE 3: High confidence + Medium risk + Reversible → Limited action (§6.3)
        elif confidence >= ETHICAL["confidence_high"] and risk_score == 2 and rev_score >= 2:
            autonomy_level   = AutonomyDecision.LIMITED_ACTION
            permitted_action = LIMITED_ACTION_MAP.get(fault_type, "reduce_load")
            reasoning = (
                f"LIMITED AUTONOMOUS ACTION AUTHORIZED. "
                f"Confidence ({confidence:.0%}) is high, but risk level is {risk_level} (score: {risk_score}/3). "
                f"Full recommended action '{recommended}' carries elevated risk. "
                f"§6.3: Safer fallback '{permitted_action}' authorized instead — it is reversible ({reversibility}). "
                f"Mission phase '{current_phase}' (criticality: {mission_criticality}). "
                f"Human review recommended before authorizing full recovery '{recommended}'."
            )
            human_message = (
                f"Limited action '{permitted_action}' applied autonomously. "
                f"Fault: {fault_type} | Confidence: {confidence:.0%} | Risk: {risk_level}. "
                f"Human approval required to authorize full recovery: '{recommended}'."
            )

        # CASE 4: High confidence + High risk → Escalate (§6.3, requires explicit approval)
        elif confidence >= ETHICAL["confidence_high"] and risk_score == 3:
            autonomy_level   = AutonomyDecision.HUMAN_ESCALATION
            permitted_action = "none"
            self.human_hold_faults.add(fault_type)
            reasoning = (
                f"HUMAN ESCALATION REQUIRED — HIGH RISK ACTION. "
                f"Confidence ({confidence:.0%}) is high, but risk level is {risk_level} (score: {risk_score}/3). "
                f"§6.3: High-risk actions require explicit human approval. "
                f"Reversibility: {reversibility} — action may not be easily undone. "
                f"§5.3: The system must never perform irreversible/high-risk actions autonomously. "
                f"Human operator must explicitly authorize '{recommended}'."
            )
            human_message = (
                f"OPERATOR APPROVAL REQUIRED for high-risk action. "
                f"Fault: {fault_type} | Confidence: {confidence:.0%} | Risk: {risk_level} | "
                f"Reversibility: {reversibility}. "
                f"Recommended action '{recommended}' requires your explicit authorization."
            )

        # CASE 5a: Medium confidence + HIGH risk → Escalate (§6.3)
        # Even though we can act, HIGH risk faults require human oversight
        # when confidence is not at the high threshold
        elif risk_score == 3:
            autonomy_level   = AutonomyDecision.HUMAN_ESCALATION
            permitted_action = "none"
            self.human_hold_faults.add(fault_type)
            reasoning = (
                f"HUMAN ESCALATION REQUIRED — HIGH RISK + MEDIUM CONFIDENCE. "
                f"Confidence ({confidence:.0%}) is in medium range — not sufficient to justify "
                f"autonomous action on a HIGH risk fault. "
                f"§6.3: High-risk faults require either high confidence OR explicit human approval. "
                f"§5.3: System must not perform high-risk actions without sufficient certainty. "
                f"Fault: {fault_type} | Risk: {risk_level} | Reversibility: {reversibility}."
            )
            human_message = (
                f"OPERATOR ACTION REQUIRED — HIGH RISK FAULT. "
                f"Fault: {fault_type} | Confidence: {confidence:.0%} (medium) | Risk: {risk_level}. "
                f"Autonomous action blocked — confidence too low for high-risk recovery. "
                f"Recommended action '{recommended}' requires your explicit authorization."
            )

        # CASE 5b: Medium confidence + LOW/MEDIUM risk → Limited reversible action (§6.3 row 2)
        else:
            autonomy_level   = AutonomyDecision.LIMITED_ACTION
            permitted_action = LIMITED_ACTION_MAP.get(fault_type, "reduce_load")
            reasoning = (
                f"LIMITED AUTONOMOUS ACTION AUTHORIZED — MEDIUM CONFIDENCE. "
                f"Confidence ({confidence:.0%}) is in medium range "
                f"({ETHICAL['confidence_medium']:.0%}–{ETHICAL['confidence_high']:.0%}). "
                f"§6.2: Diagnosis plausible but uncertain — only reversible fallback authorized. "
                f"Action '{permitted_action}' is reversible ({reversibility}) and low-impact. "
                f"§5.5: Prioritizing graceful degradation over aggressive recovery. "
                f"Human review recommended for full recovery authorization."
            )
            human_message = (
                f"Limited action '{permitted_action}' applied (medium confidence). "
                f"Fault: {fault_type} | Confidence: {confidence:.0%}. "
                f"Human review recommended — confidence insufficient for full recovery '{recommended}'."
            )

        result = EthicalDecisionResult(
            subsystem           = diagnosis.subsystem,
            autonomy_level      = autonomy_level,
            permitted_action    = permitted_action,
            confidence          = confidence,
            risk_level          = risk_level,
            reversibility       = reversibility,
            mission_criticality = mission_criticality,
            mission_phase       = current_phase,
            reasoning           = reasoning,
            human_message       = human_message,
            requires_human_hold = autonomy_level == AutonomyDecision.HUMAN_ESCALATION,
        )

        self.decision_history.append(result)
        return result

    def to_dict(self, result: EthicalDecisionResult) -> dict:
        return {
            "subsystem":           result.subsystem,
            "autonomy_level":      result.autonomy_level,
            "permitted_action":    result.permitted_action,
            "confidence":          result.confidence,
            "risk_level":          result.risk_level,
            "reversibility":       result.reversibility,
            "mission_criticality": result.mission_criticality,
            "mission_phase":       result.mission_phase,
            "reasoning":           result.reasoning,
            "human_message":       result.human_message,
            "requires_human_hold": result.requires_human_hold,
        }