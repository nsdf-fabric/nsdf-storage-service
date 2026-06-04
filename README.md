# NSDF Storage Service

INTERSECT storage service for NSDF/CHESS workflows. It receives directed
INTERSECT messages, writes local JSON state files, uploads those files to
S3-compatible storage, and can serve a live dashboard from the same service
process.

## What It Provides

- INTERSECT capability: `nsdf_storage`
- Message endpoints:
  - `new_measurement`
  - `next_point`
  - `surrogate_values`
- Local persistence:
  - `data.json`
  - `next_x.json`
  - `surrogate.json`
- S3 persistence through a retrying upload outbox.
- Integrated FastAPI dashboard at `/dashboard`.
- WebSocket live updates at `/ws/state`.
- Debug/API endpoints for current state and local JSON files.

The Docker image now runs the integrated FastAPI application by default. The
legacy INTERSECT-only CLI is still available.

## Architecture

The preferred runtime is one Python process:

1. FastAPI/Uvicorn is the main process.
2. FastAPI lifespan starts the INTERSECT service.
3. INTERSECT handlers write JSON locally with atomic writes.
4. The in-memory live state is updated immediately.
5. WebSocket clients receive a pushed state update.
6. S3 upload is queued in a durable local outbox and retried in the background.

Dashboard updates do not wait for S3. If S3 upload is pending or failed, the
dashboard still shows the latest local data and displays a persistence banner.

## Installation

```bash
uv sync
```

## Configuration

Configuration is JSON. You do not need an `.env` file unless you prefer to
manage secrets separately and inject them into a generated JSON config.

Example local config:

```json
{
  "intersect": {
    "brokers": [
      {
        "username": "intersect_username",
        "password": "intersect_password",
        "host": "127.0.0.1",
        "port": 5672,
        "protocol": "amqp0.9.1"
      }
    ]
  },
  "intersect-hierarchy": {
    "organization": "chess",
    "facility": "chess-facility",
    "system": "storage-system",
    "subsystem": "storage-subsystem",
    "service": "nsdf-storage-service"
  },
  "s3": {
    "aws_access_key_id": "",
    "aws_secret_access_key": "",
    "endpoint_url": "https://s3.example.com",
    "bucket": "scientistcloud",
    "prefix": "myprefix",
    "data_dir": "./test-chess"
  },
  "dashboard": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 8059,
    "route": "/dashboard",
    "grid_size": null,
    "grid_bounds": null
  },
  "persistence": {
    "show_unpersisted_updates": true,
    "retry_interval_seconds": 5,
    "max_retry_interval_seconds": 60
  }
}
```

For Docker Compose, use broker host `"broker"` and data dir `"/app/data"`.

### Dashboard Grid Options

By default, the dashboard infers grid dimensions from the unique `labx` and
`labz` values in `dataset_x`.

To set a fixed grid from config:

```json
"dashboard": {
  "grid_size": [26, 26],
  "grid_bounds": [[0, 26], [0, 26]]
}
```

If `grid_size` is set and `grid_bounds` is omitted or `null`, bounds default to
`[[0, width], [0, height]]`.

You can also change the grid directly in the dashboard UI. The dashboard override
is saved in browser local storage and applies immediately without restarting the
service.

## Running The Integrated Service

Start a broker:

```bash
docker compose up broker
```

Start the FastAPI + INTERSECT + dashboard service:

```bash
uv run nsdf-storage-service-web \
  --config local-conf.json \
  --host 0.0.0.0 \
  --port 8059
```

Open the dashboard:

```text
http://localhost:8059/dashboard
```

The dashboard shows:

- measurement mask heatmap
- estimate/surrogate heatmap
- variance/uncertainty heatmap
- white dots for measured points
- yellow triangles for all suggested next points
- red star for the latest suggested next point
- persistence status for `data.json`, `next_x.json`, and `surrogate.json`

## Dashboard/API Endpoints

```text
GET /health
GET /dashboard
GET /api/state
GET /api/meta
GET /api/data.json
GET /api/surrogate.json
GET /api/next_x.json
WS  /ws/state
```

`/api/state` returns the full live state snapshot plus dashboard configuration.
`/api/meta` returns revision counters and S3 persistence status only.

## Sending Demo Updates

Use the live demo sender to exercise all three endpoints and watch the dashboard
update:

```bash
uv run python examples/send_live_dashboard_updates.py \
  --config local-conf.json \
  --cycles 8 \
  --interval 2
```

The demo behaves like a small optimization loop:

1. Sends a measurement snapshot.
2. Sends a suggested next point.
3. Sends surrogate/uncertainty values.
4. On the next cycle, the previous suggested point becomes the newest measured
   point.
5. A new next point is suggested.

## INTERSECT Message Endpoints

### `new_measurement`

Writes `data.json`. The main snapshot shape is:

```json
{
  "dataset_x": [
    [1.0, 2.0],
    [3.0, 4.0]
  ],
  "dataset_y": [69.1, 69.2],
  "backend": "sklearn",
  "kernel": "rbf",
  "bounds": [
    [0.0, 10.0],
    [0.0, 10.0]
  ],
  "dim_x": 2
}
```

Each `dataset_x[i]` is `[labx, labz]`; `dataset_y[i]` is the measured value at
that coordinate.

The endpoint also accepts point-shaped payloads used by some campaign wiring:

```json
{
  "next_x": [1.0, 2.0],
  "next_y": 69.1
}
```

or:

```json
{
  "labx": 1.0,
  "labz": 2.0,
  "center_value": 69.1
}
```

Those point shapes are accumulated into the current local snapshot.

### `next_point`

Appends to `next_x.json` grouped by workflow:

```json
{
  "workflow_id": "workflow-id",
  "data": [1.0, 2.0]
}
```

Persisted `next_x.json` shape:

```json
[
  {
    "workflow_id": "workflow-id",
    "data": [
      [1.0, 2.0],
      [3.0, 4.0]
    ]
  }
]
```

The dashboard overlays all next points and highlights the globally latest point.

### `surrogate_values`

Writes `surrogate.json`:

```json
{
  "workflow_id": "workflow-id",
  "data": [
    [69.1, 69.2],
    [0.1, 0.2],
    [0.01, 0.02]
  ]
}
```

The first list becomes `surrogate`, the second becomes `uncertainty`, and the
optional third list becomes `raw_uncertainty`.

## Persistence And S3

The live service writes local JSON first, then queues S3 upload.

On local write success:

- dashboard updates immediately
- file status becomes `pending`
- upload job is written to `upload_outbox.json`

On S3 success:

- file status becomes `persisted`
- dashboard status updates

On S3 failure:

- file status becomes `failed`
- latest local data remains visible
- outbox keeps retrying

If S3 credentials are omitted in the integrated service, dashboard updates still
work, but S3 persistence will show failed/retrying status.

## Legacy INTERSECT-Only CLI

The original CLI remains available:

```bash
uv run nsdf-storage-service --config local-conf.json
```

This mode uses the legacy lifecycle loop and does not serve the dashboard.

## Standalone Measurement Client

The package under `client/` sends a single `new_measurement` snapshot:

```bash
cd client
uv run nsdf-storage-client --config ../local-conf.json
```

With custom values:

```bash
uv run nsdf-storage-client --config ../local-conf.json \
  --dataset-x '[[10.5, 20.3], [11.0, 21.0]]' \
  --dataset-y '[42.0, 43.0]' \
  --bounds '[[0.0, 50.0], [0.0, 50.0]]' \
  --dim-x 2
```

## Docker

Build:

```bash
docker build -t nsdf-storage-service .
```

Run the full compose stack:

```bash
docker compose up --build
```

The service exposes the dashboard on:

```text
http://localhost:8059/dashboard
```

Compose mounts:

- `./local-docker-conf.json:/app/local-conf.json:ro`
- `nsdf-storage-data:/app/data`

The mounted `/app/data` volume preserves JSON state and the upload outbox across
container restarts.

## Development

```bash
uv sync
uv run pytest tests/
uv run ruff check .
uv run ruff format --check .
```

Current test coverage includes:

- data models
- endpoint behavior
- live state normalization/revisions
- atomic JSON writes
- upload outbox success/failure/retry behavior
- FastAPI state/meta/raw JSON/WebSocket startup behavior
- integrated live capability writes/state/outbox behavior
