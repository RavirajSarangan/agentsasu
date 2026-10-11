"""Fan-out of core events to every connected UI window."""

from __future__ import annotations

import asyncio

from fastapi import WebSocket

from .protocol import CoreEvent, core_event_adapter


class Hub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def add(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.add(ws)

    async def remove(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def emit(self, event: CoreEvent) -> None:
        data = core_event_adapter.dump_json(event).decode()
        async with self._lock:
            clients = list(self._clients)
        for ws in clients:
            try:
                await ws.send_text(data)
            except Exception:
                await self.remove(ws)
