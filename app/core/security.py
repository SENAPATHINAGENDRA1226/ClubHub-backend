import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pwd_bytes = plain_password.encode("utf-8")
    hash_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(pwd_bytes, hash_bytes)


def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def create_access_token(
    subject: Any,
    role: str,
    committee_ids: Optional[List[str]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode: Dict[str, Any] = {
        "exp": expire,
        "sub": str(subject),
        "role": str(role),
        "type": "access",
        "jti": str(uuid.uuid4()),
    }
    if committee_ids is not None:
        to_encode["committee_ids"] = [str(c) for c in committee_ids]

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    subject: Any,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode: Dict[str, Any] = {
        "exp": expire,
        "sub": str(subject),
        "role": str(role),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
    }
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
