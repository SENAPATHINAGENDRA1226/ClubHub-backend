import uuid
from typing import Callable, List, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_async_session
from app.core.security import decode_token
from app.models.committee import CommitteeAdmin
from app.models.misc import RevokedToken
from app.models.user import User

security_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_async_session),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise credentials_exception

    token_type = payload.get("type")
    if token_type != "access":
        raise credentials_exception

    jti = payload.get("jti")
    if jti:
        revoked_res = await db.execute(select(RevokedToken).filter_by(jti=jti))
        if revoked_res.scalars().first():
            raise credentials_exception

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise credentials_exception

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    query = (
        select(User)
        .options(
            selectinload(User.student_profile),
            selectinload(User.admin_profile),
            selectinload(User.committee_admins),
        )
        .filter(User.id == user_id)
    )
    result = await db.execute(query)
    user = result.scalars().first()

    if not user:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    return user


def require_role(*allowed_roles: str) -> Callable:
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
        if user_role_val not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required role: {allowed_roles}",
            )
        return current_user

    return role_checker


async def verify_committee_access(
    current_user: User,
    target_committee_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    user_role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if user_role_val == "admin":
        return

    if user_role_val == "committee":
        # Check assigned committee_admins
        user_cids = [ca.committee_id for ca in current_user.committee_admins] if current_user.committee_admins else []
        if target_committee_id in user_cids:
            return

        # Fallback check DB directly
        ca_res = await db.execute(
            select(CommitteeAdmin).filter_by(
                user_id=current_user.id,
                committee_id=target_committee_id,
            )
        )
        if ca_res.scalars().first():
            return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Not an administrator for this committee",
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Operation not permitted",
    )


def require_committee_scope(committee_id: Optional[uuid.UUID] = None) -> Callable:
    async def scope_checker(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session),
    ) -> User:
        if committee_id is not None:
            await verify_committee_access(current_user, committee_id, db)
        else:
            user_role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
            if user_role_val not in ("admin", "committee"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Operation not permitted",
                )
        return current_user

    return scope_checker
