import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import WebSocket

logger = logging.getLogger("devops_monitor")


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, server_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(server_id, set()).add(websocket)
        logger.info("WebSocket connected for server %s", server_id)

    def disconnect(self, server_id: str, websocket: WebSocket) -> None:
        if server_id in self._connections:
            self._connections[server_id].discard(websocket)
            if not self._connections[server_id]:
                del self._connections[server_id]

    async def broadcast(self, server_id: str, message: dict) -> None:
        connections = self._connections.get(server_id, set()).copy()
        if not connections:
            return
        payload = json.dumps(message, default=str)
        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(server_id, ws)

    async def broadcast_all(self, message: dict) -> None:
        for server_id in list(self._connections.keys()):
            await self.broadcast(server_id, message)


ws_manager = ConnectionManager()
