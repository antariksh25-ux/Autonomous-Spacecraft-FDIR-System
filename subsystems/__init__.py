"""
subsystems
==========
Modular FDIR subsystem implementations.

Architecture per subsystem:
  simulator.py  — generates sensor telemetry each tick (physics model)
  isolator.py   — fault signature library

Shared components (subsystems/base.py):
  SubsystemMonitor  — three-state anomaly detection (§5.2)
  SubsystemIsolator — signature-based fault isolation + confidence scoring
"""

from .base import (
    HealthStatus,
    FaultDiagnosis,
    ParameterMonitor,
    SubsystemMonitor,
    SubsystemIsolator,
)
