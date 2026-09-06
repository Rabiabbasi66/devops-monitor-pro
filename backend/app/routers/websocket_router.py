from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from ..utils.security import decode_token
from ..services.websocket_manager import ws_manager
from ..repositories.server_repository import ServerRepository

router = APIRouter(tags=["WebSocket"])
server_repo = ServerRepository()


@router.websocket("/ws/servers/{server_id}")
async def websocket_endpoint(websocket: WebSocket, server_id: str, token: str):
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=1008)
        return

    user_id = payload.get("sub")
    server = await server_repo.get_by_id(server_id, user_id)
    if not server:
        await websocket.close(code=1008)
        return

    await ws_manager.connect(server_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(server_id, websocket)
