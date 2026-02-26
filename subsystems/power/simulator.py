"""
subsystems/power/simulator.py
==============================
Simulates Power Subsystem sensor readings on a normalized 0-100 scale.

Sensors: voltage, current, soc (state of charge), temperature (regulator)

Realistic behaviour:
  - Fault progression rate varies randomly (models real degradation)
  - Gaussian noise (realistic sensor distribution)
  - Recovery drift (backup stabilises at slightly lower voltage)
  - Cross-coupling: voltage drop stresses battery; overcurrent generates heat
"""

import random
import config as cfg

NOMINAL   = cfg.POWER_NOMINAL
NOISE_AMP = cfg.POWER_NOISE_AMPLITUDE


class PowerSubsystemSimulator:

    def __init__(self):
        self.voltage     = float(NOMINAL["voltage"]["nominal"])
        self.current     = float(NOMINAL["current"]["nominal"])
        self.soc         = float(NOMINAL["soc"]["nominal"])
        self.temperature = float(NOMINAL["temperature"]["nominal"])

        self.active_faults = {}
        self.recovery_mode = False
        self.backup_active = False

        self._backup_voltage_nominal = NOMINAL["voltage"]["nominal"] * 0.94

    def inject_fault(self, fault_config: dict):
        fault_type = fault_config["type"]
        self.active_faults[fault_type] = {
            **fault_config,
            "progress": 0.0,
            "base_step": random.uniform(0.08, 0.18),
        }

    def apply_recovery(self, recovery_action: str):
        self.recovery_mode = True
        primary_map = {
            "switch_to_backup_regulator": "voltage_drop",
            "emergency_charge":           "battery_drain",
            "safe_mode":                  None,
        }
        limited_map = {
            "reduce_load": ["voltage_drop", "overcurrent"],
        }

        if recovery_action in primary_map:
            target = primary_map[recovery_action]
            if target is None:
                self.active_faults.clear()
            else:
                self.active_faults.pop(target, None)
        elif recovery_action in limited_map:
            for ft in limited_map[recovery_action]:
                if ft in self.active_faults:
                    self.active_faults[ft]["_rate_limited"] = True

        if recovery_action == "switch_to_backup_regulator":
            self.backup_active = True

    def _gaussian_noise(self, amplitude: float) -> float:
        return random.gauss(0, amplitude * 0.5)

    def _apply_active_faults(self):
        for fault_type, fault in list(self.active_faults.items()):
            severity  = fault.get("severity", "gradual")
            target    = fault["target_value"]
            base_step = fault.get("base_step", 0.12)

            if severity == "sudden":
                step = 1.0
            else:
                step = base_step + random.gauss(0, base_step * 0.3)
                step = max(0.02, step)

            if fault.get("_rate_limited"):
                step *= random.uniform(0.4, 0.6)

            fault["progress"] = min(1.0, fault["progress"] + step)
            t = fault["progress"]

            if fault_type == "voltage_drop":
                self.voltage = NOMINAL["voltage"]["nominal"] + t * (target - NOMINAL["voltage"]["nominal"])
                if self.voltage < 45:
                    self.soc = max(0.0, self.soc - random.uniform(0.05, 0.15))

            elif fault_type == "overcurrent":
                self.current = NOMINAL["current"]["nominal"] + t * (target - NOMINAL["current"]["nominal"])
                heat = (self.current - NOMINAL["current"]["nominal"]) * 0.08
                self.temperature = min(100.0, self.temperature + heat * random.uniform(0.8, 1.2))

            elif fault_type == "battery_drain":
                drain = random.uniform(1.8, 3.2) * t
                self.soc = max(0.0, self.soc - drain)
                if self.soc < 40:
                    self.voltage = max(0.0, self.voltage - random.uniform(0.1, 0.3))

            elif fault_type == "thermal_overload":
                self.temperature = NOMINAL["temperature"]["nominal"] + t * (target - NOMINAL["temperature"]["nominal"])
                self.current = min(100.0, self.current + random.uniform(0.0, 0.5))

    def _apply_recovery_drift(self):
        voltage_target = (
            self._backup_voltage_nominal if self.backup_active
            else NOMINAL["voltage"]["nominal"]
        )
        rate = random.uniform(0.08, 0.16)

        self.voltage     += (voltage_target                    - self.voltage)     * rate
        self.current     += (NOMINAL["current"]["nominal"]     - self.current)     * rate
        self.soc         += min(0.3, (NOMINAL["soc"]["nominal"] - self.soc)        * 0.03)
        self.temperature += (NOMINAL["temperature"]["nominal"] - self.temperature) * rate

    def tick(self) -> dict:
        if self.active_faults:
            self._apply_active_faults()
        if self.recovery_mode:
            self._apply_recovery_drift()

        self.voltage     = max(0.0, min(100.0, self.voltage))
        self.current     = max(0.0, min(100.0, self.current))
        self.soc         = max(0.0, min(100.0, self.soc))
        self.temperature = max(0.0, min(100.0, self.temperature))

        return {
            "voltage":       round(self.voltage     + self._gaussian_noise(NOISE_AMP), 2),
            "current":       round(self.current     + self._gaussian_noise(NOISE_AMP), 2),
            "soc":           round(self.soc         + self._gaussian_noise(NOISE_AMP * 0.5), 2),
            "temperature":   round(self.temperature + self._gaussian_noise(NOISE_AMP * 0.5), 2),
            "backup_active": self.backup_active,
        }

    def reset(self):
        self.__init__()
