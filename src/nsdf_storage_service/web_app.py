from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from intersect_sdk import IntersectService, IntersectServiceConfig

from . import s3_uploader
from .config import load_config
from .dashboard.strain_lib import state_to_dashboard_payload
from .endpoints import DATA_FILE, NEXT_X_FILE, SURROGATE_FILE, StorageEndpointHandlers
from .live_state import LiveStateStore
from .service import NsdfStorageCapability
from .upload_outbox import UploadOutbox
from .websocket_manager import WebSocketManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PACKAGE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = PACKAGE_DIR / "dashboard"


class StrictS3Uploader:
    def upload_file(self, file_name: str) -> bool:
        return s3_uploader.upload_file_or_raise(file_name)


def create_app(
    *,
    config_path: str | Path | None = None,
    start_intersect: bool = True,
) -> FastAPI:
    config_file = Path(
        config_path or os.environ.get("NSDF_STORAGE_SERVICE_CONFIG_FILE", "local-conf.json")
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        raw_config = _load_config_or_exit(config_file)
        s3_uploader.init_s3(raw_config.get("s3", {}))
        data_dir = s3_uploader.uploader_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)

        live_state = LiveStateStore()
        _load_initial_state(live_state, data_dir)

        websocket_manager = WebSocketManager()
        websocket_manager.bind_loop(asyncio.get_running_loop())
        persistence_config = raw_config.get("persistence", {})
        upload_outbox = UploadOutbox(
            data_dir=data_dir,
            uploader=StrictS3Uploader(),
            live_state=live_state,
            websocket_manager=websocket_manager,
            retry_interval_seconds=float(persistence_config.get("retry_interval_seconds", 5)),
            max_retry_interval_seconds=float(
                persistence_config.get("max_retry_interval_seconds", 60)
            ),
        )
        handlers = StorageEndpointHandlers(
            data_dir=data_dir,
            live_state=live_state,
            upload_outbox=upload_outbox,
            websocket_manager=websocket_manager,
        )

        intersect_service = None
        if start_intersect:
            service_config = IntersectServiceConfig(
                hierarchy=raw_config["intersect-hierarchy"],
                **raw_config["intersect"],
            )
            capability = NsdfStorageCapability(handlers=handlers)
            intersect_service = IntersectService([capability], service_config)
            intersect_service.startup()

        app.state.config = raw_config
        app.state.config_path = config_file
        app.state.data_dir = data_dir
        app.state.live_state = live_state
        app.state.websocket_manager = websocket_manager
        app.state.upload_outbox = upload_outbox
        app.state.intersect_service = intersect_service
        app.state.handlers = handlers

        ws_task = asyncio.create_task(websocket_manager.run())
        outbox_task = asyncio.create_task(upload_outbox.run())
        app.state.background_tasks = [ws_task, outbox_task]
        try:
            yield
        finally:
            upload_outbox.stop()
            await websocket_manager.close()
            for task in app.state.background_tasks:
                task.cancel()
            await asyncio.gather(*app.state.background_tasks, return_exceptions=True)
            if intersect_service is not None:
                intersect_service.shutdown("FastAPI application shutdown")

    app = FastAPI(title="NSDF Storage Service", lifespan=lifespan)
    app.mount(
        "/static",
        StaticFiles(directory=str(DASHBOARD_DIR / "static")),
        name="static",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard() -> str:
        return (DASHBOARD_DIR / "templates" / "index.html").read_text(encoding="utf-8")

    @app.get("/api/state")
    def api_state() -> JSONResponse:
        state = _state_for_dashboard(app)
        return JSONResponse(state)

    @app.get("/api/meta")
    def api_meta() -> dict[str, Any]:
        return app.state.live_state.meta()

    @app.get("/api/data.json")
    def api_data_json() -> JSONResponse:
        return _read_local_json(app.state.data_dir / DATA_FILE)

    @app.get("/api/surrogate.json")
    def api_surrogate_json() -> JSONResponse:
        return _read_local_json(app.state.data_dir / SURROGATE_FILE)

    @app.get("/api/next_x.json")
    def api_next_x_json() -> JSONResponse:
        return _read_local_json(app.state.data_dir / NEXT_X_FILE)

    @app.websocket("/ws/state")
    async def websocket_state(websocket: WebSocket) -> None:
        manager: WebSocketManager = app.state.websocket_manager
        await manager.connect(websocket, _state_for_dashboard(app))
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await manager.disconnect(websocket)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="NSDF Storage FastAPI service")
    parser.add_argument(
        "--config",
        type=Path,
        default=os.environ.get("NSDF_STORAGE_SERVICE_CONFIG_FILE", "local-conf.json"),
    )
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    raw_config = _load_config_or_exit(args.config)
    dashboard_config = raw_config.get("dashboard", {})
    host = args.host or dashboard_config.get("host", "0.0.0.0")
    port = args.port or int(dashboard_config.get("port", 8059))
    app = create_app(config_path=args.config)
    uvicorn.run(app, host=host, port=port, workers=1)


def _load_config_or_exit(path: Path) -> dict[str, Any]:
    try:
        return load_config(path)
    except (ValueError, OSError) as exc:
        logger.critical("Unable to load config file: %s", exc)
        sys.exit(1)


def _load_initial_state(live_state: LiveStateStore, data_dir: Path) -> None:
    live_state.load_initial(
        measurement=_read_json_if_exists(data_dir / DATA_FILE, expected=dict),
        surrogate=_read_json_if_exists(data_dir / SURROGATE_FILE, expected=dict),
        next_x=_read_json_if_exists(data_dir / NEXT_X_FILE, expected=list),
    )


def _read_json_if_exists(path: Path, *, expected: type) -> Any:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("Ignoring unreadable startup JSON file: %s", path, exc_info=True)
        return None
    return data if isinstance(data, expected) else None


def _read_local_json(path: Path) -> JSONResponse:
    data = _read_json_if_exists(path, expected=dict)
    if data is None and path.name == NEXT_X_FILE:
        data = _read_json_if_exists(path, expected=list)
    if data is None:
        raise HTTPException(status_code=404, detail=f"{path.name} not found")
    return JSONResponse(data)


def _safe_dashboard_payload(state: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return state_to_dashboard_payload(state)
    except Exception as exc:
        logger.warning("Failed to build dashboard payload: %s", exc)
        return None


def _state_for_dashboard(app: FastAPI) -> dict[str, Any]:
    state = app.state.live_state.snapshot()
    state["dashboard_config"] = _dashboard_config(app.state.config)
    state["dashboard"] = _safe_dashboard_payload(state)
    return state


def _dashboard_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    dashboard = raw_config.get("dashboard", {})
    grid_size = dashboard.get("grid_size")
    if not isinstance(grid_size, list) or len(grid_size) != 2:
        grid_size = dashboard.get("fixed_grid_size")
    if isinstance(grid_size, list) and len(grid_size) == 2:
        try:
            width = int(grid_size[0])
            height = int(grid_size[1])
        except (TypeError, ValueError):
            grid_size = None
        else:
            grid_size = [max(1, width), max(1, height)]
    else:
        grid_size = None
    grid_bounds = _grid_bounds_from_dashboard_config(dashboard, grid_size)
    return {
        "grid_size": grid_size,
        "grid_bounds": grid_bounds,
    }


def _grid_bounds_from_dashboard_config(
    dashboard: dict[str, Any],
    grid_size: list[int] | None,
) -> list[list[int]] | None:
    configured = dashboard.get("grid_bounds")
    if isinstance(configured, list) and len(configured) >= 2:
        try:
            x0, x1 = int(configured[0][0]), int(configured[0][1])
            z0, z1 = int(configured[1][0]), int(configured[1][1])
        except (TypeError, ValueError, IndexError):
            return None
        return [[x0, x1], [z0, z1]]
    if grid_size is None:
        return None
    return [[0, grid_size[0]], [0, grid_size[1]]]


app = create_app()


if __name__ == "__main__":
    main()
