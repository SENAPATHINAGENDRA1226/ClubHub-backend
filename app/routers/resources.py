import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_async_session
from app.core.deps import require_role
from app.models.content import Resource
from app.models.user import User
from app.schemas.resources import PaginatedResourcesResponse, ResourceCreate, ResourceResponse, ResourceUpdate
from app.services.broadcast import broadcast_event

router = APIRouter(prefix="/api/resources", tags=["Resources"])


@router.get("", response_model=PaginatedResourcesResponse)
async def list_resources(
    category: Optional[str] = Query(None, description="Category filter e.g. DSA, Web Dev, AI/ML"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
):
    query = select(Resource)
    count_query = select(func.count(Resource.id))

    if category:
        query = query.filter(func.lower(Resource.category) == category.lower())
        count_query = count_query.filter(func.lower(Resource.category) == category.lower())

    query = query.order_by(Resource.created_at.desc())

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    res = await db.execute(query.limit(limit).offset(offset))
    items = res.scalars().all()

    return PaginatedResourcesResponse(
        items=[ResourceResponse.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{resource_id}", response_model=ResourceResponse)
async def get_resource(
    resource_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Resource).filter_by(id=resource_id))
    resource = res.scalars().first()
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    return resource


@router.post("", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED)
async def create_resource(
    body: ResourceCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    resource = Resource(
        **body.model_dump(),
        added_by=current_user.id,
    )
    db.add(resource)
    await db.commit()
    await db.refresh(resource)

    payload = ResourceResponse.model_validate(resource).model_dump(mode="json")
    await broadcast_event("resource.created", payload)
    return resource


@router.put("/{resource_id}", response_model=ResourceResponse)
async def update_resource(
    resource_id: uuid.UUID,
    body: ResourceUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Resource).filter_by(id=resource_id))
    resource = res.scalars().first()
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    for f, v in body.model_dump(exclude_unset=True).items():
        setattr(resource, f, v)

    await db.commit()
    await db.refresh(resource)

    payload = ResourceResponse.model_validate(resource).model_dump(mode="json")
    await broadcast_event("resource.updated", payload)
    return resource


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(
    resource_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Resource).filter_by(id=resource_id))
    resource = res.scalars().first()
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    r_id_str = str(resource.id)
    await db.delete(resource)
    await db.commit()

    await broadcast_event("resource.deleted", {"resource_id": r_id_str})
    return None
