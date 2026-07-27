import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_async_session
from app.core.deps import get_current_user, require_role, verify_committee_access
from app.models.committee import Committee, CommitteeAdmin, CommitteeMember
from app.models.enums import CommitteeCategory, CommitteeSubCategory
from app.models.user import User
from app.schemas.committees import (
    CommitteeCreate,
    CommitteeMemberCreate,
    CommitteeMemberResponse,
    CommitteeMemberUpdate,
    CommitteeResponse,
    CommitteeUpdate,
)
from app.services.audit import write_audit_log
from app.services.broadcast import broadcast

router = APIRouter(prefix="/api/committees", tags=["Committees"])


@router.get("/my-scope", response_model=List[CommitteeResponse])
async def get_my_committee_scope(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    user_role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

    if user_role_val == "admin":
        res = await db.execute(
            select(Committee).options(selectinload(Committee.members))
        )
        return res.scalars().all()

    if user_role_val == "committee":
        ca_res = await db.execute(
            select(CommitteeAdmin).filter_by(user_id=current_user.id)
        )
        c_ids = [ca.committee_id for ca in ca_res.scalars().all()]
        if not c_ids:
            return []

        res = await db.execute(
            select(Committee)
            .options(selectinload(Committee.members))
            .filter(Committee.id.in_(c_ids))
        )
        return res.scalars().all()

    return []


@router.get("", response_model=List[CommitteeResponse])
async def list_committees(
    category: Optional[CommitteeCategory] = Query(None, description="Faculty or Student category"),
    sub_category: Optional[CommitteeSubCategory] = Query(None, description="Sub-category filter"),
    db: AsyncSession = Depends(get_async_session),
):
    query = select(Committee).options(selectinload(Committee.members))
    if category:
        query = query.filter(Committee.category == category)
    if sub_category:
        query = query.filter(Committee.sub_category == sub_category)

    res = await db.execute(query)
    committees = res.scalars().all()
    return committees


@router.get("/{committee_id}", response_model=CommitteeResponse)
async def get_committee(
    committee_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
):
    query = select(Committee).options(selectinload(Committee.members)).filter_by(id=committee_id)
    res = await db.execute(query)
    committee = res.scalars().first()
    if not committee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Committee not found")
    return committee


@router.get("/{committee_id}/members", response_model=List[CommitteeMemberResponse])
async def get_committee_members(
    committee_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
):
    query = select(CommitteeMember).filter_by(committee_id=committee_id).order_by(CommitteeMember.order_index.asc())
    res = await db.execute(query)
    members = res.scalars().all()
    return members


@router.post("", response_model=CommitteeResponse, status_code=status.HTTP_201_CREATED)
async def create_committee(
    body: CommitteeCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    committee = Committee(**body.model_dump())
    db.add(committee)
    await db.commit()
    await db.refresh(committee)

    res = await db.execute(
        select(Committee).options(selectinload(Committee.members)).filter_by(id=committee.id)
    )
    full_comm = res.scalars().first()
    payload = CommitteeResponse.model_validate(full_comm).model_dump(mode="json")

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="created",
        entity_type="committee",
        entity_id=committee.id,
        payload={"name": committee.name},
    )

    await broadcast(
        channel="committees",
        event_type="committees.committee.created",
        entity_id=str(committee.id),
        action="created",
        payload=payload,
    )

    return full_comm


@router.put("/{committee_id}", response_model=CommitteeResponse)
async def update_committee(
    committee_id: uuid.UUID,
    body: CommitteeUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Committee).filter_by(id=committee_id))
    committee = res.scalars().first()
    if not committee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Committee not found")

    for f, v in body.model_dump(exclude_unset=True).items():
        setattr(committee, f, v)

    await db.commit()
    await db.refresh(committee)

    full_res = await db.execute(
        select(Committee).options(selectinload(Committee.members)).filter_by(id=committee.id)
    )
    full_comm = full_res.scalars().first()
    payload = CommitteeResponse.model_validate(full_comm).model_dump(mode="json")

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="updated",
        entity_type="committee",
        entity_id=committee.id,
        payload={"name": committee.name},
    )

    await broadcast(
        channel="committees",
        event_type="committees.committee.updated",
        entity_id=str(committee.id),
        action="updated",
        payload=payload,
    )

    return full_comm


@router.delete("/{committee_id}", response_model=CommitteeResponse)
async def delete_committee(
    committee_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(
        select(Committee).options(selectinload(Committee.members)).filter_by(id=committee_id)
    )
    committee = res.scalars().first()
    if not committee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Committee not found")

    response_data = CommitteeResponse.model_validate(committee).model_dump(mode="json")
    c_id_str = str(committee.id)
    c_name = committee.name

    await db.delete(committee)
    await db.commit()

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="deleted",
        entity_type="committee",
        payload={"name": c_name, "committee_id": c_id_str},
    )

    await broadcast(
        channel="committees",
        event_type="committees.committee.deleted",
        entity_id=c_id_str,
        action="deleted",
        payload={"committee_id": c_id_str, "name": c_name},
    )

    return CommitteeResponse(**response_data)


@router.post("/{committee_id}/members", response_model=CommitteeMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_committee_member(
    committee_id: uuid.UUID,
    body: CommitteeMemberCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    await verify_committee_access(current_user, committee_id, db)

    c_res = await db.execute(select(Committee).filter_by(id=committee_id))
    committee = c_res.scalars().first()
    if not committee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Committee not found")

    matched_user = None
    if body.user_id:
        u_res = await db.execute(select(User).filter_by(id=body.user_id))
        matched_user = u_res.scalars().first()
    elif body.email and body.email.strip():
        u_res = await db.execute(select(User).filter_by(email=body.email.strip().lower()))
        matched_user = u_res.scalars().first()

    member = CommitteeMember(
        committee_id=committee_id,
        user_id=matched_user.id if matched_user else body.user_id,
        full_name=body.full_name,
        email=body.email or (matched_user.email if matched_user else ""),
        role_title=body.role_title,
        photo_url=body.photo_url,
        bio=body.bio,
        order_index=body.order_index,
    )
    db.add(member)

    if matched_user:
        ca_res = await db.execute(
            select(CommitteeAdmin).filter_by(user_id=matched_user.id, committee_id=committee_id)
        )
        if not ca_res.scalars().first():
            db.add(CommitteeAdmin(user_id=matched_user.id, committee_id=committee_id))

        user_role_str = str(matched_user.role.value if hasattr(matched_user.role, "value") else matched_user.role)
        if user_role_str == "student":
            matched_user.role = UserRole.COMMITTEE

    await db.commit()
    await db.refresh(member)

    payload = CommitteeMemberResponse.model_validate(member).model_dump(mode="json")

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="created",
        entity_type="committee_member",
        entity_id=member.id,
        payload={"full_name": member.full_name, "committee_id": str(committee_id)},
    )

    await broadcast(
        channel="committees",
        event_type="committees.member.created",
        entity_id=str(member.id),
        action="created",
        payload=payload,
    )

    return member



# Separate router prefix for committee member direct mutations
member_router = APIRouter(prefix="/api/committee-members", tags=["Committee Members"])


@member_router.put("/{member_id}", response_model=CommitteeMemberResponse)
async def update_committee_member(
    member_id: uuid.UUID,
    body: CommitteeMemberUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(CommitteeMember).filter_by(id=member_id))
    member = res.scalars().first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Committee member not found")

    await verify_committee_access(current_user, member.committee_id, db)

    for f, v in body.model_dump(exclude_unset=True).items():
        setattr(member, f, v)

    await db.commit()
    await db.refresh(member)

    payload = CommitteeMemberResponse.model_validate(member).model_dump(mode="json")

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="updated",
        entity_type="committee_member",
        entity_id=member.id,
        payload={"full_name": member.full_name, "committee_id": str(member.committee_id)},
    )

    await broadcast(
        channel="committees",
        event_type="committees.member.updated",
        entity_id=str(member.id),
        action="updated",
        payload=payload,
    )

    return member


@member_router.delete("/{member_id}", response_model=CommitteeMemberResponse)
async def delete_committee_member(
    member_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(CommitteeMember).filter_by(id=member_id))
    member = res.scalars().first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Committee member not found")

    await verify_committee_access(current_user, member.committee_id, db)

    response_data = CommitteeMemberResponse.model_validate(member).model_dump(mode="json")
    m_id_str = str(member.id)
    c_id_str = str(member.committee_id)
    m_name = member.full_name

    await db.delete(member)
    await db.commit()

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="deleted",
        entity_type="committee_member",
        payload={"full_name": m_name, "committee_id": c_id_str, "member_id": m_id_str},
    )

    await broadcast(
        channel="committees",
        event_type="committees.member.deleted",
        entity_id=m_id_str,
        action="deleted",
        payload={"member_id": m_id_str, "committee_id": c_id_str},
    )

    return CommitteeMemberResponse(**response_data)
