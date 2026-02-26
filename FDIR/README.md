# FDIR System (Backend + Dashboard)

This is a **real ingestion-first FDIR system**:

- The backend **does not generate** telemetry and does not ship “demo scenarios”.
- You **push real telemetry** into the backend.
- The system performs deterministic **Detection → Isolation → Ethical Gate → Recovery Recommendation** and streams results to the dashboard.

## Run

### Backend (FastAPI)

From the `FDIR/` folder:

```powershell
./start-backend.ps1
```

Backend URLs:

- REST: http://localhost:8001/api
- Docs: http://localhost:8001/docs
- WebSocket: ws://localhost:8001/ws

### Frontend (Next.js)

From the `FDIR/` folder:

```powershell
./start-frontend.ps1
```

Dashboard:

- http://localhost:3000

### Full stack

```powershell
./start-all.ps1
```

## Ingest telemetry (no mock data)

The backend processes telemetry only after you ingest it.

### REST ingest

- `POST /api/telemetry`
- `POST /api/telemetry/batch`

Request shape:

```json
{
  "timestamp_iso": "<iso8601>",
  "values": {
    "<channel>": 0.0
  }
}
```

### Dashboard ingest

The dashboard includes an upload panel that accepts:

- JSON array of samples
- JSON Lines (one sample per line)

Each sample supports either `{ timestamp_iso, values }` or a flat object with numeric channel fields.

## Configuration

Channel definitions (units, nominal ranges, risk classification) can be overridden in:

- [FDIR/fdir_config.yaml](fdir_config.yaml)

## Data persistence

The backend persists received telemetry, faults, and logs in:

- `FDIR/data/fdir.db`
