import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.core.security import decode_token
from app.ws.manager import ws_manager

logger = logging.getLogger("clubhub.ws_router")
router = APIRouter(tags=["WebSockets"])


@router.websocket("/ws/updates")
async def websocket_updates_endpoint(websocket: WebSocket, token: Optional[str] = None):
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = payload.get("sub", "anonymous")
    role = payload.get("role", "student")

    await ws_manager.connect(websocket, user_id=user_id, role=role)

    try:
        while True:
            # Handle incoming ping / messages keepalive
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"[WS ERROR] {e}")
        await ws_manager.disconnect(websocket)
