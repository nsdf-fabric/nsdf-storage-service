# NSDF Storage Service

INTERSECT Storage Service for NSDF. Receives directed CHESS and DIAL messages,
writes their payloads to local JSON files, and uploads those files to S3.

## Architecture Role

This service is the **INTERSECT Storage Service** in the CHESS autonomous
experiment loop:

1. `intersect-chess-data-service` monitors reduced CHESS data sources.
2. A caller sends this service a directed INTERSECT message containing the full
   DIAL workflow state from `get_workflow_data`.
3. DIAL can send next-point and surrogate prediction results.
4. **This service** registers an `nsdf_storage` capability with message endpoints
   for `new_measurement`, `next_point`, and `surrogate_values`.
5. Each endpoint writes a JSON file and uploads it to the configured S3 bucket.

The `data.json` file is overwritten on every `new_measurement` message because
that payload already contains the full `dataset_x` and `dataset_y` history.
The service also groups next-point results by workflow in `next_x.json`; surrogate grids
are stored as the latest payload in `surrogate.json`.

## Installation

```bash
uv sync
```

## Usage

### As an INTERSECT Service

```bash
# Start with local config
nsdf-storage-service --config local-conf.json

# Or with Docker
docker compose up
```

### CLI Usage

The `nsdf-storage-service` command is installed as a console script:

```bash
# Use the default config file (local-conf.json)
nsdf-storage-service

# Specify a config file
nsdf-storage-service --config /path/to/config.json

# Or set via environment variable
export NSDF_STORAGE_SERVICE_CONFIG_FILE=/path/to/config.json
nsdf-storage-service
```

### Standalone Test Client

A standalone INTERSECT client is available under `client/` for sending
test workflow snapshots:

```bash
cd client
uv run nsdf-storage-client --config ../local-conf.json

# With custom values
uv run nsdf-storage-client --config ../local-conf.json \
  --dataset-x '[[10.5, 20.3], [11.0, 21.0]]' \
  --dataset-y '[42.0, 43.0]' \
  --bounds '[[0.0, 50.0], [0.0, 50.0]]' \
  --dim-x 2
```

The client connects to the same broker, and sends a single
`nsdf_storage.new_measurement` message.

### INTERSECT Message Endpoints

- `describe()` — Returns a short description of the service behavior
- `new_measurement(NewMeasurementData)` — Writes the full DIAL workflow snapshot
  to `data.json` and uploads to S3
- `next_point(NextPointData)` — Appends a DIAL next-point vector to the matching
  workflow in `next_x.json` and uploads to S3
- `surrogate_values(SurrogateValuesData)` — Writes the latest DIAL surrogate and
  uncertainty values to `surrogate.json` and uploads to S3
- `status()` — Returns `"Up"`

Callers should send a directed INTERSECT message to capability `nsdf_storage`,
endpoint `new_measurement`, with payload:

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

For CHESS workflows, each `dataset_x` row contains the old `[labx, labz]`
coordinates, and `dataset_y` contains the old `center_value` values aligned by
index.

DIAL next-point payloads should use the DIAL response shape from
`get_next_point`:

```json
{
  "workflow_id": "workflow-id",
  "data": [1.0, 2.0]
}
```

The persisted `next_x.json` groups received vectors by `workflow_id`:

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

DIAL surrogate payloads should use the DIAL response shape from
`get_surrogate_values`. The first list is surrogate/predicted values, the second
is transformed uncertainty, and the optional third list is raw uncertainty:

```json
{
  "workflow_id": "workflow-id",
  "data": [
    [1.0, 2.0],
    [0.1, 0.2],
    [0.01, 0.02]
  ]
}
```

## Configuration

The local config follows the same broker shape as `intersect-chess-data-service`,
with an additional `s3` section:

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
    "data_dir": "/app/data"
  }
}
```

## Running With the Test Client

Start a RabbitMQ broker, the storage service, and the test client in separate
terminals:

```bash
# Terminal 1 — broker
docker compose up broker

# Terminal 2 — storage service
uv run nsdf-storage-service --config local-conf.json

# Terminal 3 — test client
cd client
uv run nsdf-storage-client --config ../local-conf.json
```

The service logs incoming messages and uploads `data.json`, `next_x.json`, or
`surrogate.json` depending on the endpoint.

## Development

```bash
# Install dev dependencies
uv sync

# Run tests
uv run pytest tests/

# Lint
uv run ruff check .
uv run ruff format --check
```

## Docker

```bash
# Build
docker build -t nsdf-storage-service .

# Run with docker-compose (includes RabbitMQ broker)
docker compose up
```
