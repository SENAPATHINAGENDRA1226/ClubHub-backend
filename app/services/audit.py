import logging
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.misc import AuditLog

logger = logging.getLogger("clubhub.audit")


async def write_audit_log(
    db: AsyncSession,
    *,
    actor_user_id: Optional[uuid.UUID],
    action: str,
    entity_type: str,
    entity_id: Optional[uuid.UUID] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """
    Write a row to audit_log for every admin mutation.
    Call this AFTER db.commit() so the main transaction is not affected by audit failures.
    """
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
    )
    db.add(entry)
    try:
        await db.commit()
        await db.refresh(entry)
        logger.info(
            f"[AUDIT] {action} on {entity_type}"
            f" (entity={entity_id}, actor={actor_user_id})"
        )
    except Exception as e:
        logger.error(f"[AUDIT WRITE FAIL] {e}")
        await db.rollback()
    return entry
