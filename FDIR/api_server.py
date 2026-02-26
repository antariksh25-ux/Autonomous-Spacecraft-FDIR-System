"""FDIR backend entrypoint.

This server is ingestion-first (no telemetry generation).

Endpoints:
- REST: http://localhost:8001/api/*
- WebSocket: ws://localhost:8001/ws

Ingest telemetry via:
- POST /api/telemetry
- POST /api/telemetry/batch
"""

from __future__ import annotations

import uvicorn

def main() -> None:
    uvicorn.run(
        "backend.api:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        log_level="info",
    )

if __name__ == "__main__":
    main()
