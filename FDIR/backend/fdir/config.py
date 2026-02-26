from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import yaml

from .types import ChannelSpec, RiskLevel


@dataclass(frozen=True)
class FDIRConfig:
    sample_rate_hz: float
    mission_phase: str
    channels: List[ChannelSpec]
    persistence_samples: int
    cross_sensor_min: int


def _default_channels() -> List[ChannelSpec]:
    return [
        ChannelSpec("voltage_1", "V", 26.0, 30.0, "power", RiskLevel.high),
        ChannelSpec("voltage_2", "V", 26.0, 30.0, "power", RiskLevel.high),
        ChannelSpec("current_1", "A", 0.0, 10.0, "power", RiskLevel.medium),
        ChannelSpec("current_2", "A", 0.0, 10.0, "power", RiskLevel.medium),
        ChannelSpec("temp_1", "C", -10.0, 55.0, "thermal", RiskLevel.high),
        ChannelSpec("temp_2", "C", -10.0, 55.0, "thermal", RiskLevel.high),
        ChannelSpec("temp_3", "C", -10.0, 55.0, "thermal", RiskLevel.high),
        ChannelSpec("temp_4", "C", -10.0, 55.0, "thermal", RiskLevel.high),
        ChannelSpec("gyro_x", "dps", -2.0, 2.0, "attitude", RiskLevel.high),
        ChannelSpec("gyro_y", "dps", -2.0, 2.0, "attitude", RiskLevel.high),
        ChannelSpec("gyro_z", "dps", -2.0, 2.0, "attitude", RiskLevel.high),
        ChannelSpec("acc_x", "m/s2", -0.2, 0.2, "attitude", RiskLevel.medium),
        ChannelSpec("acc_y", "m/s2", -0.2, 0.2, "attitude", RiskLevel.medium),
        ChannelSpec("acc_z", "m/s2", -0.2, 0.2, "attitude", RiskLevel.medium),
        ChannelSpec("signal_strength", "dB", -100.0, -50.0, "communication", RiskLevel.medium),
        ChannelSpec("packet_loss", "%", 0.0, 2.0, "communication", RiskLevel.high),
        ChannelSpec("latency", "ms", 0.0, 450.0, "communication", RiskLevel.medium),
    ]


def load_config(repo_root: Path) -> FDIRConfig:
    """Load config from `FDIR/fdir_config.yaml` if present, else use defaults."""

    cfg_path = repo_root / "FDIR" / "fdir_config.yaml"
    if not cfg_path.exists():
        return FDIRConfig(
            sample_rate_hz=2.0,
            mission_phase="nominal",
            channels=_default_channels(),
            persistence_samples=3,
            cross_sensor_min=2,
        )

    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    sample_rate_hz = float(raw.get("sample_rate_hz", 2.0))
    mission_phase = str(raw.get("mission_phase", "nominal"))
    persistence_samples = int(raw.get("persistence_samples", 3))
    cross_sensor_min = int(raw.get("cross_sensor_min", 2))

    channels: List[ChannelSpec] = []
    for ch in raw.get("channels", []) or []:
        risk_raw = str(ch.get("risk", "low")).lower()
        risk = RiskLevel(risk_raw) if risk_raw in RiskLevel._value2member_map_ else RiskLevel.low
        channels.append(
            ChannelSpec(
                name=str(ch["name"]),
                unit=str(ch.get("unit", "")),
                nominal_min=float(ch["nominal_min"]),
                nominal_max=float(ch["nominal_max"]),
                subsystem=str(ch.get("subsystem", "unknown")).lower(),
                risk=risk,
            )
        )

    if not channels:
        channels = _default_channels()

    return FDIRConfig(
        sample_rate_hz=sample_rate_hz,
        mission_phase=mission_phase,
        channels=channels,
        persistence_samples=persistence_samples,
        cross_sensor_min=cross_sensor_min,
    )


def channel_index(channels: List[ChannelSpec]) -> Dict[str, ChannelSpec]:
    return {c.name: c for c in channels}
