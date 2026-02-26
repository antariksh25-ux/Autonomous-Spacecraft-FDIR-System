from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    raw = raw.strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except Exception:
        return default


def _parse_origins(raw: str | None) -> List[str]:
    if not raw:
        return ["http://localhost:3000"]
    raw = raw.strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    log_level: str
    allow_origins: List[str]

    simulation_enabled: bool
    simulation_autostart: bool
    simulation_seed: int

    broadcast_hz: float


def load_settings() -> Settings:
    return Settings(
        host=os.getenv("HOST", "0.0.0.0"),
        port=_env_int("PORT", 8001),
        log_level=os.getenv("LOG_LEVEL", "info"),
        allow_origins=_parse_origins(os.getenv("FDIR_ALLOW_ORIGINS")),
        simulation_enabled=_env_bool("FDIR_SIMULATION", True),
        simulation_autostart=_env_bool("FDIR_SIM_AUTOSTART", True),
        simulation_seed=_env_int("FDIR_SIM_SEED", 7),
        broadcast_hz=_env_float("FDIR_BROADCAST_HZ", 1.0),
    )
