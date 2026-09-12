import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import WebSocket

logger = logging.getLogger("devops_monitor")


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._user_connections: Dict[str, Set[str]] = {}  # user_id -> set of server_ids

    async def connect(self, server_id: str, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        self._connections.setdefault(server_id, set()).add(websocket)
        self._user_connections.setdefault(user_id, set()).add(server_id)
        logger.info("WebSocket connected for server %s by user %s", server_id, user_id)

    def disconnect(self, server_id: str, websocket: WebSocket, user_id: str) -> None:
        if server_id in self._connections:
            self._connections[server_id].discard(websocket)
            if not self._connections[server_id]:
                del self._connections[server_id]
        
        if user_id in self._user_connections:
            self._user_connections[user_id].discard(server_id)
            if not self._user_connections[user_id]:
                del self._user_connections[user_id]

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
            self.disconnect(server_id, ws, "unknown")  # user_id unknown during disconnect cleanup

    async def broadcast_all(self, message: dict) -> None:
        for server_id in list(self._connections.keys()):
            await self.broadcast(server_id, message)

    async def broadcast_to_user(self, user_id: str, message: dict) -> None:
        """Broadcast message to all servers belonging to a user."""
        server_ids = self._user_connections.get(user_id, set())
        for server_id in server_ids:
            await self.broadcast(server_id, message)

    def get_connection_count(self, server_id: str) -> int:
        """Get number of active connections for a server."""
        return len(self._connections.get(server_id, set()))

    def get_user_connection_count(self, user_id: str) -> int:
        """Get total number of connections for a user."""
        server_ids = self._user_connections.get(user_id, set())
        return sum(self.get_connection_count(sid) for sid in server_ids)


ws_manager = ConnectionManager()
