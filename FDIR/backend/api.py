from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .fdir.config import load_config
from .fdir.simulator import SpacecraftSimulator
from .fdir.system import FDIRSystem
from .fdir.types import TelemetrySample
from .settings import load_settings


class TelemetryIngestRequest(BaseModel):
    timestamp_iso: str = Field(..., description="ISO-8601 timestamp for the sample")
    values: Dict[str, float] = Field(..., description="Map of channel -> numeric value")


class TelemetryBatchRequest(BaseModel):
    samples: List[TelemetryIngestRequest]


class InjectFaultRequest(BaseModel):
    fault: str = Field(..., description="Fault name")
    magnitude: float = Field(1.0, description="Fault magnitude scaling")
    duration_s: float = Field(12.0, description="How long the fault persists")


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        async with self._lock:
            clients = list(self._clients)

        dead: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    async def count(self) -> int:
        async with self._lock:
            return len(self._clients)


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title="FDIR Backend", version="2.1")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allow_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    fdir_root = Path(__file__).resolve().parents[1]
    config = load_config(fdir_root)
    system = FDIRSystem(config=config, data_dir=fdir_root / "data")
    ws_mgr = ConnectionManager()

    web_concurrency = int(os.getenv("WEB_CONCURRENCY", "1") or "1")
    simulation_enabled = bool(settings.simulation_enabled)
    if simulation_enabled and web_concurrency > 1:
        # Running simulation + sqlite in multiple worker processes will cause duplicate streams and DB contention.
        simulation_enabled = False
        system.add_log(
            "warning",
            "startup",
            "Simulation disabled because WEB_CONCURRENCY > 1",
            {"web_concurrency": web_concurrency},
        )

    simulator = SpacecraftSimulator(seed=settings.simulation_seed)
    sim_running = bool(settings.simulation_autostart and simulation_enabled)
    sim_lock = asyncio.Lock()
    stop_event = asyncio.Event()
    sim_task: Optional[asyncio.Task] = None
    heartbeat_task: Optional[asyncio.Task] = None

    last_broadcast_log_seq = 0
    last_broadcast_total_samples = 0

    async def _broadcast_snapshot(snap: Dict[str, Any]) -> None:
        nonlocal last_broadcast_log_seq, last_broadcast_total_samples

        # Send only *new* logs since last broadcast (global) to avoid UI duplication.
        logs = system.list_logs(since_seq=last_broadcast_log_seq, limit=200)["logs"]
        if logs:
            last_broadcast_log_seq = max(int(l.get("seq", 0)) for l in logs)
        else:
            last_broadcast_log_seq = max(last_broadcast_log_seq, int(snap.get("log_seq", last_broadcast_log_seq)))

        ts = snap.get("telemetry_state") or {}
        if isinstance(ts, dict):
            last_broadcast_total_samples = int(ts.get("total_samples") or last_broadcast_total_samples)

        await ws_mgr.broadcast({"type": "snapshot", **{**snap, "logs": logs}})

    def _sim_status() -> Dict[str, Any]:
        return {
            "enabled": bool(simulation_enabled),
            "running": bool(sim_running),
            "fault": simulator.fault_status(),
        }

    async def _sim_loop() -> None:
        nonlocal sim_running
        dt = 1.0 / max(0.1, float(config.sample_rate_hz))
        while not stop_event.is_set():
            if simulation_enabled and sim_running:
                async with sim_lock:
                    values = simulator.step(dt)
                snap = system.ingest(TelemetrySample(timestamp_iso=SpacecraftSimulator.now_iso(), values=values))
                await _broadcast_snapshot(snap)
            await asyncio.sleep(dt)

    async def _heartbeat_loop() -> None:
        # When simulation is paused/disabled, keep UI alive with periodic snapshots.
        while not stop_event.is_set():
            await asyncio.sleep(1.0 / max(0.1, float(settings.broadcast_hz)))
            if await ws_mgr.count() <= 0:
                continue
            snap = system.snapshot(include_logs=False)
            ts = snap.get("telemetry_state") or {}
            total = int(ts.get("total_samples") or 0) if isinstance(ts, dict) else 0
            if total == last_broadcast_total_samples:
                await _broadcast_snapshot(snap)

    @app.on_event("startup")
    async def _startup() -> None:
        nonlocal sim_task, heartbeat_task
        if simulation_enabled:
            sim_task = asyncio.create_task(_sim_loop())
        heartbeat_task = asyncio.create_task(_heartbeat_loop())

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        stop_event.set()
        for t in [sim_task, heartbeat_task]:
            if t:
                t.cancel()

    @app.get("/api/config")
    async def get_config() -> Dict[str, Any]:
        return {
            "sample_rate_hz": config.sample_rate_hz,
            "mission_phase": config.mission_phase,
            "channels": [
                {
                    "name": c.name,
                    "unit": c.unit,
                    "nominal_min": c.nominal_min,
                    "nominal_max": c.nominal_max,
                    "subsystem": c.subsystem,
                    "risk": c.risk.value,
                }
                for c in config.channels
            ],
        }

    @app.get("/healthz")
    async def healthz() -> Dict[str, Any]:
        return {"ok": True, "service": "fdir-backend", "version": app.version}

    @app.get("/readyz")
    async def readyz() -> Dict[str, Any]:
        # Minimal readiness: process can create snapshots and access config.
        _ = system.snapshot(include_logs=False)
        return {"ok": True}

    @app.get("/api/status")
    async def get_status() -> Dict[str, Any]:
        snap = system.snapshot(include_logs=False)
        return {
            "mode": snap["mode"],
            "mission_phase": snap["mission_phase"],
            "fault_count": snap["fault_count"],
            "log_seq": snap["log_seq"],
            "telemetry": snap["telemetry_state"],
            "sim": _sim_status(),
        }

    @app.get("/api/sim/status")
    async def sim_status() -> Dict[str, Any]:
        return _sim_status()

    @app.post("/api/control/sim/start")
    async def sim_start() -> Dict[str, Any]:
        nonlocal sim_running
        if not simulation_enabled:
            return {"ok": False, "error": "simulation_disabled", "sim": _sim_status()}
        sim_running = True
        return {"ok": True, "sim": _sim_status()}

    @app.post("/api/control/sim/stop")
    async def sim_stop() -> Dict[str, Any]:
        nonlocal sim_running
        if not simulation_enabled:
            return {"ok": False, "error": "simulation_disabled", "sim": _sim_status()}
        sim_running = False
        return {"ok": True, "sim": _sim_status()}

    @app.post("/api/control/inject")
    async def inject_fault(req: InjectFaultRequest) -> Dict[str, Any]:
        if not simulation_enabled:
            return {"ok": False, "error": "simulation_disabled", "sim": _sim_status()}
        async with sim_lock:
            simulator.inject_fault(name=req.fault, magnitude=req.magnitude, duration_s=req.duration_s)
        system.add_log(
            "warning",
            "inject",
            f"Injected fault: {req.fault}",
            {"magnitude": req.magnitude, "duration_s": req.duration_s},
        )
        return {"ok": True, "sim": _sim_status()}

    @app.post("/api/control/inject/clear")
    async def clear_injection() -> Dict[str, Any]:
        if not simulation_enabled:
            return {"ok": False, "error": "simulation_disabled", "sim": _sim_status()}
        async with sim_lock:
            simulator.clear_fault()
        system.add_log("info", "inject", "Cleared injected fault")
        return {"ok": True, "sim": _sim_status()}

    @app.get("/api/faults")
    async def get_faults(limit: int = 50) -> Dict[str, Any]:
        return system.list_faults(limit=limit)

    @app.get("/api/logs")
    async def get_logs(since: int = 0, limit: int = 200) -> Dict[str, Any]:
        return system.list_logs(since_seq=since, limit=limit)

    @app.post("/api/control/reset")
    async def reset() -> Dict[str, Any]:
        return system.reset()

    @app.post("/api/telemetry")
    async def ingest_telemetry(req: TelemetryIngestRequest) -> Dict[str, Any]:
        snap = system.ingest(TelemetrySample(timestamp_iso=req.timestamp_iso, values=req.values))
        await _broadcast_snapshot(snap)
        return {"ok": True, "log_seq": snap["log_seq"]}

    @app.post("/api/telemetry/batch")
    async def ingest_batch(req: TelemetryBatchRequest) -> Dict[str, Any]:
        last: Optional[Dict[str, Any]] = None
        for s in req.samples:
            last = system.ingest(TelemetrySample(timestamp_iso=s.timestamp_iso, values=s.values))
        if last is None:
            return {"ok": True, "processed": 0}
        await _broadcast_snapshot(last)
        return {"ok": True, "processed": len(req.samples), "log_seq": last["log_seq"]}

    @app.websocket("/ws")
    async def ws(ws: WebSocket) -> None:
        await ws_mgr.connect(ws)
        try:
            await ws.send_json(
                {
                    "type": "init",
                    "config": await get_config(),
                    "status": await get_status(),
                    "logs": system.snapshot(include_logs=True, logs_limit=200)["logs"],
                    "sim": _sim_status(),
                }
            )
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await ws_mgr.disconnect(ws)

    return app


app = create_app()
