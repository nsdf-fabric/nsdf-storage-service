FROM python:3.11-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md /app/
COPY src /app/src

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

COPY local-conf.json /app/local-conf.json

EXPOSE 8059

CMD ["nsdf-storage-service-web", "--config", "/app/local-conf.json", "--host", "0.0.0.0", "--port", "8059"]
