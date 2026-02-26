"""FDIR backend entrypoint.

Default behavior is simulation-first (synthetic telemetry generator) with optional fault injection.
You can disable simulation for production ingestion-only mode via env vars.

Endpoints:
- REST: http://<host>:<port>/api/*
- Health: http://<host>:<port>/healthz and /readyz
- WebSocket: ws://<host>:<port>/ws
"""

from __future__ import annotations

import uvicorn

from backend.settings import load_settings

def main() -> None:
    settings = load_settings()
    uvicorn.run(
        "backend.api:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level,
    )

if __name__ == "__main__":
    main()
