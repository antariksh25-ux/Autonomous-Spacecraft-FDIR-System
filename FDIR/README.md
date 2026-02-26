# FDIR System (Backend + Dashboard)

This is a deterministic FDIR system with a built-in simulator:

- **Simulation-first by default**: the backend can generate synthetic (physics-ish) telemetry and stream snapshots to the dashboard.
- **No ML model**: detection/isolation/ethics/recovery are rule-based and explainable.
- **Ingestion is still supported**: you can push real telemetry via REST if you disable simulation.

## Run

### Backend (FastAPI)

From the `FDIR/` folder:

```powershell
./start-backend.ps1
```

Backend URLs:

- REST: http://localhost:8001/api
- Docs: http://localhost:8001/docs
- Health: http://localhost:8001/healthz and http://localhost:8001/readyz
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

## Simulation & fault injection

The dashboard includes buttons to inject faults into the simulator:

- `power_regulator_failure`
- `thermal_runaway`
- `communication_dropout`
- `attitude_drift`

You can also control this over REST:

- `POST /api/control/sim/start`
- `POST /api/control/sim/stop`
- `POST /api/control/inject`
- `POST /api/control/inject/clear`

## Ingest real telemetry (optional)

If you want ingestion-only mode (recommended for production), disable simulation and push real telemetry.

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

## VM hosting (systemd + nginx + SSL)

If you are hosting the backend on a Linux VM with a domain + SSL:

- Follow [FDIR/deploy/README_VM.md](deploy/README_VM.md)

### Recommended production env vars

- `PORT` (set by App Runner; defaults to 8001 locally)
- `FDIR_ALLOW_ORIGINS` (comma-separated, e.g. `https://your-frontend-domain`)
- `FDIR_SIMULATION=0` (disable simulator in production)
- `WEB_CONCURRENCY=1` (SQLite-safe default)

If you keep simulation enabled, do not scale worker processes > 1.

## Configuration

Channel definitions (units, nominal ranges, risk classification) can be overridden in:

- [FDIR/fdir_config.yaml](fdir_config.yaml)

## Data persistence

The backend persists received telemetry, faults, and logs in:

- `FDIR/data/fdir.db`
