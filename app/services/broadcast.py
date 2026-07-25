import logging
from typing import Any, Dict, Optional
from app.ws.manager import ws_manager

logger = logging.getLogger("clubhub.broadcast")


async def broadcast(
    channel: str,
    event_type: str,
    entity_id: Optional[str] = None,
    action: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Standardized broadcast function.
    All routers must use this with explicit channel + event_type from the channel map.
    """
    logger.info(
        f"[BROADCAST] Channel: {channel} | Event: {event_type} | Entity: {entity_id}"
    )
    await ws_manager.broadcast_to_channel(
        channel=channel,
        event_type=event_type,
        entity_id=entity_id,
        action=action or event_type.split(".")[-1] if "." in (event_type or "") else action,
        payload=payload or {},
    )


# Keep backward-compatible alias during migration
async def broadcast_event(
    channel_or_event_type: str = "global",
    event_type_or_payload: Any = None,
    entity_id: Optional[str] = None,
    action: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    channel: Optional[str] = None,
    event_type: Optional[str] = None,
) -> None:
    """Backward-compatible wrapper. New code should use broadcast() directly."""
    final_channel = channel or channel_or_event_type
    final_event_type = event_type or str(event_type_or_payload or channel_or_event_type)

    if isinstance(event_type_or_payload, dict):
        final_event_type = channel_or_event_type
        payload_data = event_type_or_payload
        # Derive channel from event_type pattern: "event.created" -> "events"
        if "." in final_event_type:
            prefix = final_event_type.split(".")[0]
            # Map singular to plural for channel names
            channel_map = {
                "event": "events",
                "user": "users",
                "committee": "committees",
                "committee_member": "committees",
                "alumni": "alumni",
                "certificate": "certificates",
                "grievance": "grievances",
                "registration": "registrations",
                "setting": "settings",
                "contact": "global",
                "opportunity": "global",
                "resource": "global",
            }
            final_channel = channel_map.get(prefix, "global")
        else:
            final_channel = "global"
        ent_id = str(payload_data.get("id") or payload_data.get("event_id") or "")
        act = final_event_type.split(".")[-1] if "." in final_event_type else "updated"
    else:
        payload_data = payload or {}
        ent_id = entity_id
        act = action

    await broadcast(
        channel=final_channel,
        event_type=final_event_type,
        entity_id=ent_id,
        action=act,
        payload=payload_data,
    )
