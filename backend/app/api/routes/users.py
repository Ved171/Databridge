from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_superadmin, get_current_admin_or_wsadmin, ROLE_RANK, get_user_rank
from app.models import User, Role, UserInviteToken, UserManagerAssignment
from app.schemas import UserOut, CreateUserRequest
from app.core.tokens import generate_invite_token, INVITE_TOKEN_TTL_HOURS
from app.core.config import settings
from app.core.security import hash_password
from typing import List
from sqlalchemy.orm import selectinload

router = APIRouter()


@router.post("/", status_code=201, response_model=UserOut)
async def create_user(
    payload: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_superadmin: User = Depends(get_current_superadmin)
):
    # 1. Check email uniqueness
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A user with this email already exists.")

    # 2. Create user with default password '123456789'
    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password("123456789"),
        department_id=payload.department_id,
        role_id=payload.role_id,
        force_password_change=True,
        is_active=True,
        token_version=1,
    )
    db.add(user)
    await db.commit()

    # Eager load the role_relation before serialization
    res = await db.execute(
        select(User).options(selectinload(User.role_relation)).where(User.id == user.id)
    )
    user = res.scalar_one()
    return user


@router.get("/", response_model=List[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(User).options(selectinload(User.role_relation)).order_by(User.created_at))
    return result.scalars().all()


@router.get("/manager-assignments")
async def list_manager_assignments(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Get all manager-member assignments to construct the org tree.
    """
    result = await db.execute(select(UserManagerAssignment))
    assignments = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "manager_user_id": str(a.manager_user_id),
            "member_user_id": str(a.member_user_id)
        }
        for a in assignments
    ]


@router.patch("/{user_id}/toggle-active", response_model=UserOut)
async def toggle_active(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_or_wsadmin),
):
    result = await db.execute(select(User).options(selectinload(User.role_relation)).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    # Hierarchy: can only affect users with lower rank
    my_rank = await get_user_rank(current_user, db)
    target_rank = await get_user_rank(user, db)
    if target_rank >= my_rank:
        raise HTTPException(status_code=403, detail="Cannot modify a user with equal or higher role")

    user.is_active = not user.is_active
    await db.flush()
    await db.refresh(user)
    return user


@router.patch("/{user_id}/make-superadmin", response_model=UserOut)
async def make_superadmin(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    result = await db.execute(select(User).options(selectinload(User.role_relation)).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Retrieve Superadmin role from DB
    role_res = await db.execute(select(Role).where(Role.slug == "superadmin"))
    superadmin_role = role_res.scalar_one_or_none()
        
    old_role_id = user.role_id
    user.is_superadmin = True
    if superadmin_role:
        user.role_id = superadmin_role.id
        
    # Write to UserRoleHistory in the same transaction
    from app.models import UserRoleHistory
    db.add(UserRoleHistory(
        user_id=user.id,
        old_role_id=old_role_id,
        new_role_id=user.role_id,
        changed_by=current_user.id
    ))
    
    await db.flush()
    await db.refresh(user)
    return user


@router.patch("/{user_id}/promote", response_model=UserOut)
async def promote_user(
    user_id: str,
    role: str = Query(..., description="Target role slug"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_or_wsadmin),
):
    """
    Promote/demote a user to a specific global role.
    Hierarchy enforced: you can only set roles lower than your own.
    """
    # Retrieve target role by slug
    role_res = await db.execute(select(Role).where(Role.slug == role, Role.deleted_at.is_(None)))
    target_role = role_res.scalar_one_or_none()
    if not target_role:
        raise HTTPException(status_code=400, detail=f"Role with slug '{role}' not found.")

    my_rank = await get_user_rank(current_user, db)
    target_role_rank = target_role.level

    # You can only set roles lower than your own rank
    if target_role_rank >= my_rank:
        raise HTTPException(status_code=403, detail=f"You cannot assign the '{role}' role - it requires higher privileges.")

    result = await db.execute(select(User).options(selectinload(User.role_relation)).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Cannot demote someone of equal or higher rank
    existing_rank = await get_user_rank(user, db)
    if existing_rank >= my_rank:
        raise HTTPException(status_code=403, detail="Cannot change role of a user with equal or higher role.")

    old_role_id = user.role_id
    user.role_id = target_role.id
    user.is_superadmin = (target_role.slug == "superadmin")

    # Log in history
    from app.models import UserRoleHistory
    db.add(UserRoleHistory(
        user_id=user.id,
        old_role_id=old_role_id,
        new_role_id=target_role.id,
        changed_by=current_user.id
    ))

    await db.flush()
    await db.refresh(user)
    return user
