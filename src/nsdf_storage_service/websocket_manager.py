from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._queue: asyncio.Queue[dict[str, Any]] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._closed = False

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._queue = asyncio.Queue()

    async def connect(self, websocket: WebSocket, initial_state: dict[str, Any]) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)
        await websocket.send_json({"type": "state_snapshot", "state": initial_state})

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    def publish(self, event_type: str, state: dict[str, Any]) -> None:
        if self._closed:
            return
        event = {
            "type": event_type,
            "revision": state.get("revision"),
            "state": state,
        }
        if self._loop is None or self._queue is None:
            return
        self._loop.call_soon_threadsafe(self._queue.put_nowait, event)

    async def run(self) -> None:
        if self._queue is None:
            self.bind_loop(asyncio.get_running_loop())
        assert self._queue is not None
        while not self._closed:
            event = await self._queue.get()
            await self.broadcast(event)

    async def broadcast(self, event: dict[str, Any]) -> None:
        async with self._lock:
            clients = list(self._clients)

        disconnected: list[WebSocket] = []
        for client in clients:
            try:
                await client.send_json(event)
            except Exception:
                logger.debug("WebSocket client disconnected during broadcast", exc_info=True)
                disconnected.append(client)

        if disconnected:
            async with self._lock:
                for client in disconnected:
                    self._clients.discard(client)

    async def close(self) -> None:
        self._closed = True
        async with self._lock:
            clients = list(self._clients)
            self._clients.clear()
        for client in clients:
            try:
                await client.close()
            except Exception:
                logger.debug("Ignoring WebSocket close failure", exc_info=True)
