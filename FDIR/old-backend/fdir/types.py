from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    green = "green"
    yellow = "yellow"
    red = "red"


class SystemMode(str, Enum):
    run = "run"
    hold = "hold"


class AutonomyDecisionLevel(str, Enum):
    monitor = "monitor"
    limited_autonomy = "limited_autonomy"
    full_autonomy = "full_autonomy"
    human_escalation = "human_escalation"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


@dataclass(frozen=True)
class ChannelSpec:
    name: str
    unit: str
    nominal_min: float
    nominal_max: float
    subsystem: str
    risk: RiskLevel


@dataclass
class TelemetrySample:
    timestamp_iso: str
    values: Dict[str, float]


@dataclass
class SensorHealth:
    channel: str
    value: float
    nominal_min: float
    nominal_max: float
    within_nominal: bool
    deviation: float


@dataclass
class SubsystemHealth:
    subsystem: str
    severity: Severity
    summary: str
    sensors: List[SensorHealth]


@dataclass
class IsolationResult:
    subsystem: str
    component: str
    fault_type: str
    severity: Severity
    confidence: float
    rationale: str


@dataclass
class EthicalDecision:
    level: AutonomyDecisionLevel
    justification: str
    risk: RiskLevel


@dataclass
class RecoveryAction:
    action: Optional[str]
    rationale: Optional[str]
    executed: bool


@dataclass
class FaultRecord:
    fault_id: str
    timestamp_iso: str
    subsystem: str
    component: str
    fault_type: str
    severity: Severity
    confidence: float
    ethical_level: AutonomyDecisionLevel
    ethical_justification: str
    action_taken: Optional[str]
    action_rationale: Optional[str]
    escalated: bool


@dataclass
class LogEntry:
    seq: int
    timestamp_iso: str
    level: str
    stage: str
    message: str
    details: Dict[str, Any]
