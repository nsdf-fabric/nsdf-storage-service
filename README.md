# NSDF Storage Service

INTERSECT Storage Service for NSDF. Listens for CHESS `new_measurement` events
and prints each payload it receives. The payload handler is intentionally small
so it can later be replaced with logic that moves payloads to an S3 bucket.

## Architecture Role

This service is the **INTERSECT Storage Service** in the CHESS autonomous
experiment loop:

1. `intersect-chess-data-service` monitors reduced CHESS data sources.
2. The data-service emits an INTERSECT `new_measurement` event containing
   `{labx, labz, center_value}`.
3. **This service** subscribes to that event through the INTERSECT SDK client
   event API while also registering its own `nsdf_storage` capability.
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
- `status()` - Returns `"Listening"` or `"Idle"`

### INTERSECT Event Subscription

By default, the service listens for:

- Source hierarchy:
  `chess.chess-facility.data-egress-system.data-egress-subsystem.chess-data-egress-service`
- Capability: `chess_data_egress`
- Event: `new_measurement`
- Payload: `{"labx": float, "labz": float, "center_value": float}`

These values can be changed in the `source-event` section of the config file.

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
  },
  "source-event": {
    "hierarchy": {
      "organization": "chess",
      "facility": "chess-facility",
      "system": "data-egress-system",
      "subsystem": "data-egress-subsystem",
      "service": "chess-data-egress-service"
    },
    "capability": "chess_data_egress",
    "event": "new_measurement"
  }
}
```

## Running With Data Service

Start a RabbitMQ broker, then run both services against matching broker
configuration:

```bash
# Terminal 1, from this repository
docker compose up broker

# Terminal 2, from ../intersect-chess-data-service
uv run intersect-chess-data-service --config local-conf.json

# Terminal 3, from this repository
uv run nsdf-storage-service --config local-conf.json
```

When the data-service emits a `new_measurement`, this service prints the event
source, capability, event name, timestamp, and payload.

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
