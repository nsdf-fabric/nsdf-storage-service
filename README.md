# NSDF Storage Service

INTERSECT Storage Service for NSDF. Receives directed CHESS `new_measurement`
messages, accumulates the measurement fields (`labx`, `labz`, `center_value`)
into a local `data.json` file, and uploads it to S3 on every measurement.

## Architecture Role

This service is the **INTERSECT Storage Service** in the CHESS autonomous
experiment loop:

1. `intersect-chess-data-service` monitors reduced CHESS data sources.
2. A caller sends this service a directed INTERSECT message containing
   `{labx, labz, center_value}`.
3. **This service** registers an `nsdf_storage` capability with a
   `new_measurement(NewMeasurementData)` message endpoint.
4. Each measurement is appended to in-memory arrays, written to
   `data.json`, and uploaded to the configured S3 bucket.

On restart, the service recovers prior measurements from the existing
`data.json` file and continues appending.

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
test measurements:

```bash
cd client
uv run nsdf-storage-client --config ../local-conf.json

# With custom values
uv run nsdf-storage-client --config ../local-conf.json --labx 10.5 --labz 20.3 --center-value 42.0
```

The client connects to the same broker, and sends a single
`nsdf_storage.new_measurement` message.

### INTERSECT Message Endpoints

- `describe()` — Returns a short description of the service behavior
- `new_measurement(NewMeasurementData)` — Appends the measurement to the
  accumulated arrays, writes `data.json`, and uploads to S3
- `status()` — Returns `"Up"`

Callers should send a directed INTERSECT message to capability `nsdf_storage`,
endpoint `new_measurement`, with payload:

```json
{
  "labx": 1.0,
  "labz": 2.0,
  "center_value": 3.0
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

The service logs each incoming measurement and uploads the accumulated
`data.json` to S3. The test client logs the service's response.

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
