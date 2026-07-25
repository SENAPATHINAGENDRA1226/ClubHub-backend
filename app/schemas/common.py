from typing import Optional
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None


class MessageResponse(BaseModel):
    message: str
