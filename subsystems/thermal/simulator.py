"""
subsystems/thermal/simulator.py
================================
Simulates Thermal Subsystem sensor readings on a normalized 0-100 scale.

Sensors:
  - internal_temp:  component bay / electronics bay temperature
  - radiator_temp:  radiator panel surface temperature
  - heater_power:   heater output level (% of max)
  - panel_temp:     external surface / solar panel temperature

Cross-coupling (optional):
  Accepts power_current hint — high current draw heats the electronics bay.

Realistic behaviour:
  - Thermal faults progress gradually (thermal inertia)
  - Gaussian noise on all sensor channels
  - Cross-coupling between parameters (runaway heats radiator, heater loss cools panel)
  - Recovery drift with variable rate (backup heater stabilises at reduced capacity)
"""

import random
import config as cfg

NOMINAL   = cfg.THERMAL_NOMINAL
NOISE_AMP = cfg.THERMAL_NOISE_AMPLITUDE


class ThermalSubsystemSimulator:

    def __init__(self):
        self.internal_temp = float(NOMINAL["internal_temp"]["nominal"])
        self.radiator_temp = float(NOMINAL["radiator_temp"]["nominal"])
        self.heater_power  = float(NOMINAL["heater_power"]["nominal"])
        self.panel_temp    = float(NOMINAL["panel_temp"]["nominal"])

        self.active_faults = {}
        self.recovery_mode = False
        self.backup_heater_active = False

    def inject_fault(self, fault_config: dict):
        fault_type = fault_config["type"]
        self.active_faults[fault_type] = {
            **fault_config,
            "progress": 0.0,
            "base_step": random.uniform(0.06, 0.14),
        }

    def apply_recovery(self, recovery_action: str):
        self.recovery_mode = True

        primary_map = {
            "thermal_throttle":            "thermal_runaway",
            "switch_to_backup_heater":     "heater_failure",
            "activate_emergency_radiator": "radiator_degradation",
            "safe_mode":                   None,
        }
        limited_map = {
            "reduce_load": ["thermal_runaway", "radiator_degradation"],
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

        if recovery_action == "switch_to_backup_heater":
            self.backup_heater_active = True

    def _gaussian_noise(self, amplitude: float) -> float:
        return random.gauss(0, amplitude * 0.5)

    def _apply_active_faults(self):
        for fault_type, fault in list(self.active_faults.items()):
            severity  = fault.get("severity", "gradual")
            target    = fault["target_value"]
            base_step = fault.get("base_step", 0.10)

            if severity == "sudden":
                step = 1.0
            else:
                step = base_step + random.gauss(0, base_step * 0.3)
                step = max(0.02, step)

            if fault.get("_rate_limited"):
                step *= random.uniform(0.4, 0.6)

            fault["progress"] = min(1.0, fault["progress"] + step)
            t = fault["progress"]

            if fault_type == "thermal_runaway":
                self.internal_temp = (
                    NOMINAL["internal_temp"]["nominal"]
                    + t * (target - NOMINAL["internal_temp"]["nominal"])
                )
                # Cross-coupling: runaway overwhelms radiator
                if self.internal_temp > 55:
                    self.radiator_temp = min(
                        100.0, self.radiator_temp + random.uniform(0.1, 0.4)
                    )

            elif fault_type == "heater_failure":
                self.heater_power = (
                    NOMINAL["heater_power"]["nominal"]
                    + t * (target - NOMINAL["heater_power"]["nominal"])
                )
                # Cross-coupling: losing heat cools external panel
                if self.heater_power < 25:
                    self.panel_temp = max(
                        0.0, self.panel_temp - random.uniform(0.15, 0.45)
                    )

            elif fault_type == "radiator_degradation":
                self.radiator_temp = (
                    NOMINAL["radiator_temp"]["nominal"]
                    + t * (target - NOMINAL["radiator_temp"]["nominal"])
                )
                # Cross-coupling: can't reject heat → internal temp rises
                if self.radiator_temp > 40:
                    self.internal_temp = min(
                        100.0, self.internal_temp + random.uniform(0.05, 0.2)
                    )

    def _apply_recovery_drift(self):
        rate = random.uniform(0.08, 0.16)
        heater_target = (
            NOMINAL["heater_power"]["nominal"] * 0.85
            if self.backup_heater_active
            else NOMINAL["heater_power"]["nominal"]
        )

        self.internal_temp += (NOMINAL["internal_temp"]["nominal"] - self.internal_temp) * rate
        self.radiator_temp += (NOMINAL["radiator_temp"]["nominal"] - self.radiator_temp) * rate
        self.heater_power  += (heater_target - self.heater_power) * rate
        self.panel_temp    += (NOMINAL["panel_temp"]["nominal"] - self.panel_temp) * rate

    def tick(self, power_current: float = None) -> dict:
        if self.active_faults:
            self._apply_active_faults()
        if self.recovery_mode:
            self._apply_recovery_drift()

        # Cross-coupling: excess power current heats electronics bay
        if power_current is not None and power_current > 35:
            excess_heat = (power_current - 35) * 0.06
            self.internal_temp += excess_heat * random.uniform(0.8, 1.2)

        # Physical bounds
        self.internal_temp = max(0.0, min(100.0, self.internal_temp))
        self.radiator_temp = max(0.0, min(100.0, self.radiator_temp))
        self.heater_power  = max(0.0, min(100.0, self.heater_power))
        self.panel_temp    = max(0.0, min(100.0, self.panel_temp))

        return {
            "internal_temp":        round(self.internal_temp + self._gaussian_noise(NOISE_AMP), 2),
            "radiator_temp":        round(self.radiator_temp + self._gaussian_noise(NOISE_AMP), 2),
            "heater_power":         round(self.heater_power  + self._gaussian_noise(NOISE_AMP * 0.5), 2),
            "panel_temp":           round(self.panel_temp    + self._gaussian_noise(NOISE_AMP * 0.5), 2),
            "backup_heater_active": self.backup_heater_active,
        }

    def reset(self):
        self.__init__()
