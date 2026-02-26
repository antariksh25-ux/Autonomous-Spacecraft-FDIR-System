"""
health_monitor.py
=================
Continuously monitors Power Subsystem sensor readings.

Implements §5.2 three-state fault detection:
  NOMINAL          → reading within normal bounds (no action)
  TEMPORARY_ANOMALY → reading crossed warning threshold but not persistent
                      (logged, not escalated — distinguishes noise from faults)
  CONFIRMED_FAULT  → deviation persisted across PERSISTENCE_WINDOW ticks
                      (triggers fault isolation pipeline)

Noise discrimination:
  Readings within NOISE_BAND of the warning threshold are treated as
  "possible noise" and need extra persistence before escalation.

§10.1 Success Metric: Transient noise must NOT trigger false fault declarations.
"""

from collections import deque
from config import ANOMALY_THRESHOLDS, NOMINAL, PERSISTENCE_WINDOW, NOISE_BAND


class HealthStatus:
    NOMINAL           = "NOMINAL"
    TEMPORARY_ANOMALY = "TEMPORARY_ANOMALY"   # §5.2 — new distinct state
    WARNING           = "WARNING"
    CRITICAL          = "CRITICAL"


class ParameterMonitor:
    """
    Single-parameter health monitor with three-state classification
    and a noise-aware persistence filter.
    """

    def __init__(self, name: str):
        self.name      = name
        self.thresholds = ANOMALY_THRESHOLDS[name]
        self.nominal    = NOMINAL[name]
        self.history    = deque(maxlen=PERSISTENCE_WINDOW)
        self.status     = HealthStatus.NOMINAL
        self.anomaly_confirmed = False

    def _raw_classify(self, value: float) -> str:
        """
        Raw classification of a single reading into NOMINAL / WARNING / CRITICAL.
        Does NOT apply persistence — that happens in update().
        """
        t = self.thresholds

        if self.name in ("current", "temperature"):   # upper-bound faults
            if value >= t["critical"]:
                return HealthStatus.CRITICAL
            elif value >= t["warning"]:
                return HealthStatus.WARNING
            else:
                return HealthStatus.NOMINAL
        else:                                          # lower-bound faults
            if value <= t["critical"]:
                return HealthStatus.CRITICAL
            elif value <= t["warning"]:
                return HealthStatus.WARNING
            else:
                return HealthStatus.NOMINAL

    def _is_near_noise_band(self, value: float) -> bool:
        """
        Returns True if the reading is within NOISE_BAND of the warning threshold.
        These readings are ambiguous — could be noise, could be early anomaly.
        """
        t = self.thresholds
        if self.name in ("current", "temperature"):
            return abs(value - t["warning"]) <= NOISE_BAND
        else:
            return abs(value - t["warning"]) <= NOISE_BAND

    def update(self, value: float) -> dict:
        """
        Process one tick. Returns health assessment dict.

        Three-state output per §5.2:
          NOMINAL           → no anomaly
          TEMPORARY_ANOMALY → reading is off but not yet confirmed
          WARNING/CRITICAL  → confirmed by persistence window
        """
        raw_class = self._raw_classify(value)
        near_noise = self._is_near_noise_band(value)
        self.history.append(raw_class)

        window_full  = len(self.history) == PERSISTENCE_WINDOW
        non_nominal  = [s for s in self.history if s != HealthStatus.NOMINAL]

        if raw_class == HealthStatus.NOMINAL:
            # Value is back in range
            self.status = HealthStatus.NOMINAL
            self.anomaly_confirmed = False

        elif not window_full:
            # Not enough history yet — temporary anomaly (§5.2)
            self.status = HealthStatus.TEMPORARY_ANOMALY
            self.anomaly_confirmed = False

        elif near_noise and len(non_nominal) < PERSISTENCE_WINDOW:
            # Value near noise band — not all window is anomalous — likely noise
            self.status = HealthStatus.TEMPORARY_ANOMALY
            self.anomaly_confirmed = False

        elif len(non_nominal) == PERSISTENCE_WINDOW:
            # Full window all anomalous → confirmed fault
            self.anomaly_confirmed = True
            if HealthStatus.CRITICAL in self.history:
                self.status = HealthStatus.CRITICAL
            else:
                self.status = HealthStatus.WARNING

        else:
            # Mixed window — partial anomaly, still temporary
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


class HealthMonitor:
    """
    Master health monitor for the Power Subsystem.
    Aggregates all parameter monitors and produces a unified health report.
    §5.1: Continuous monitoring.
    §5.7: Resource-aware — simple comparisons only, no ML.
    """

    def __init__(self):
        self.monitors = {
            param: ParameterMonitor(param)
            for param in ("voltage", "current", "soc", "temperature")
        }
        self.tick_count = 0

    def process(self, sensor_data: dict) -> dict:
        """Process one tick of sensor data. Returns unified health report."""
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

        # Overall status = worst individual status
        all_statuses = [r["status"] for r in parameter_reports.values()]
        if HealthStatus.CRITICAL in all_statuses:
            overall_status = HealthStatus.CRITICAL
        elif HealthStatus.WARNING in all_statuses:
            overall_status = HealthStatus.WARNING
        elif HealthStatus.TEMPORARY_ANOMALY in all_statuses:
            overall_status = HealthStatus.TEMPORARY_ANOMALY
        else:
            overall_status = HealthStatus.NOMINAL

        return {
            "tick":                self.tick_count,
            "overall_status":      overall_status,
            "confirmed_anomalies": confirmed_anomalies,
            "temporary_anomalies": temporary_anomalies,   # §5.2 distinct state
            "has_anomaly":         len(confirmed_anomalies) > 0,
            "has_temporary":       len(temporary_anomalies) > 0,
            "parameters":          parameter_reports,
            "backup_active":       sensor_data.get("backup_active", False),
        }

    def reset_parameter(self, param: str):
        """Clear a parameter's history after recovery."""
        if param in self.monitors:
            self.monitors[param].history.clear()
            self.monitors[param].status = HealthStatus.NOMINAL
            self.monitors[param].anomaly_confirmed = False

    def reset_all(self):
        """Full reset (used by /reset API endpoint)."""
        for param in self.monitors:
            self.reset_parameter(param)
        self.tick_count = 0