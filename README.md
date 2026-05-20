# NSDF Storage Service

INTERSECT Storage Service for NSDF. Receives directed CHESS `new_measurement`
messages through an INTERSECT service endpoint and prints each payload it
receives. The payload handler is intentionally small so it can later be replaced
with logic that moves payloads to an S3 bucket.

## Architecture Role

This service is the **INTERSECT Storage Service** in the CHESS autonomous
experiment loop:

1. `intersect-chess-data-service` monitors reduced CHESS data sources.
2. A caller sends this service a directed INTERSECT message containing
   `{labx, labz, center_value}`.
3. **This service** registers an `nsdf_storage` capability with a
   `new_measurement(NewMeasurementData)` message endpoint.
4. The current handler prints the payload. A future handler will move the
   payload to an S3 bucket.

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

### INTERSECT Message Endpoints

- `describe()` - Returns a short description of the service behavior
- `new_measurement(NewMeasurementData)` - Receives and prints a CHESS
  measurement payload
- `status()` - Returns `"Up"`

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

The local config follows the same broker shape as `intersect-chess-data-service`:

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
  }
}
```

## Running With Data Service

Start a RabbitMQ broker, then run this service and a caller that sends directed
messages to `nsdf_storage.new_measurement`:

```bash
# Terminal 1, from this repository
docker compose up broker

# Terminal 2, from this repository
uv run nsdf-storage-service --config local-conf.json
```

When a directed `new_measurement` message arrives, this service prints the
message source, capability, endpoint name, timestamp, and payload. A plain
INTERSECT event emitted by another service is not consumed by this branch.

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
