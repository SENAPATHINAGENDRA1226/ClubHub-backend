import asyncio
import logging
from typing import Any, Dict, Optional, Set
from fastapi import WebSocket

logger = logging.getLogger("clubhub.ws")


class ConnectionManager:
    def __init__(self):
        # Maps WebSocket -> metadata dict {"user_id": ..., "role": ..., "channels": set()}
        self.active_connections: Dict[WebSocket, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str, role: str):
        await websocket.accept()
        async with self._lock:
            self.active_connections[websocket] = {
                "user_id": user_id,
                "role": role,
                "channels": {
                    "events", "registrations", "dashboard", "certificates",
                    "users", "committees", "alumni", "grievances", "settings",
                    "global",
                },
            }
        logger.info(f"[WS CONNECTED] User: {user_id} ({role}) | Total active: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                user_id = self.active_connections[websocket]["user_id"]
                del self.active_connections[websocket]
                logger.info(f"[WS DISCONNECTED] User: {user_id} | Total active: {len(self.active_connections)}")

    async def subscribe(self, websocket: WebSocket, channel: str):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections[websocket]["channels"].add(channel)

    async def broadcast_to_channel(
        self,
        channel: str,
        event_type: str,
        entity_id: Optional[str] = None,
        action: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ):
        message = {
            "channel": channel,
            "event_type": event_type,
            "entity_id": entity_id,
            "action": action,
            "payload": payload or {},
            "timestamp": asyncio.get_event_loop().time(),
        }

        async with self._lock:
            targets = [
                ws
                for ws, meta in self.active_connections.items()
                if channel == "global" or channel in meta["channels"]
            ]

        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"[WS SEND FAIL] {e}")

        logger.info(f"[WS BROADCAST] Channel: {channel} | Event: {event_type} | Recipients: {len(targets)}")


ws_manager = ConnectionManager()
