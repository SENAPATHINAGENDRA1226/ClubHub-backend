import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_async_session
from app.core.deps import require_role
from app.models.content import MediaItem
from app.models.enums import MediaItemType
from app.models.user import User
from app.schemas.media import (
    MediaItemCreate,
    MediaItemResponse,
    MediaItemUpdate,
    PaginatedMediaItemsResponse,
)
from app.services.broadcast import broadcast_event

router = APIRouter(prefix="/api/media", tags=["Media Items"])


@router.get("", response_model=PaginatedMediaItemsResponse)
async def list_media_items(
    type: Optional[MediaItemType] = Query(None, description="Newsletter or Magazine type"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
):
    query = select(MediaItem)
    count_query = select(func.count(MediaItem.id))

    if type:
        query = query.filter(MediaItem.type == type)
        count_query = count_query.filter(MediaItem.type == type)

    query = query.order_by(MediaItem.published_date.desc(), MediaItem.created_at.desc())

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    res = await db.execute(query.limit(limit).offset(offset))
    items = res.scalars().all()

    return PaginatedMediaItemsResponse(
        items=[MediaItemResponse.model_validate(m) for m in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_media_file(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("admin")),
):
    uploads_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "media", "uploads"
    )
    os.makedirs(uploads_dir, exist_ok=True)

    safe_filename = f"{uuid.uuid4().hex}_{os.path.basename(file.filename)}"
    file_path = os.path.join(uploads_dir, safe_filename)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    return {
        "file_url": f"/media/uploads/{safe_filename}",
        "filename": file.filename,
    }


@router.get("/{media_id}", response_model=MediaItemResponse)
async def get_media_item(
    media_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(MediaItem).filter_by(id=media_id))
    item = res.scalars().first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media item not found")
    return item


@router.post("", response_model=MediaItemResponse, status_code=status.HTTP_201_CREATED)
async def create_media_item(
    body: MediaItemCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    media_item = MediaItem(
        **body.model_dump(),
        uploaded_by=current_user.id,
    )
    db.add(media_item)
    await db.commit()
    await db.refresh(media_item)

    payload = MediaItemResponse.model_validate(media_item).model_dump(mode="json")
    await broadcast_event("media.created", payload)
    return media_item


@router.put("/{media_id}", response_model=MediaItemResponse)
async def update_media_item(
    media_id: uuid.UUID,
    body: MediaItemUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(MediaItem).filter_by(id=media_id))
    media_item = res.scalars().first()
    if not media_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media item not found")

    for f, v in body.model_dump(exclude_unset=True).items():
        setattr(media_item, f, v)

    await db.commit()
    await db.refresh(media_item)

    payload = MediaItemResponse.model_validate(media_item).model_dump(mode="json")
    await broadcast_event("media.updated", payload)
    return media_item


@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media_item(
    media_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(MediaItem).filter_by(id=media_id))
    media_item = res.scalars().first()
    if not media_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media item not found")

    m_id_str = str(media_item.id)
    await db.delete(media_item)
    await db.commit()

    await broadcast_event("media.deleted", {"media_id": m_id_str})
    return None
