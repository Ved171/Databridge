from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_superadmin, get_current_admin_or_wsadmin, ROLE_RANK, get_user_rank
from app.models import User
from app.schemas import UserOut
from typing import List

router = APIRouter()


@router.get("/", response_model=List[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    result = await db.execute(select(User).order_by(User.created_at))
    return result.scalars().all()


@router.patch("/{user_id}/toggle-active", response_model=UserOut)
async def toggle_active(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_or_wsadmin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    # Hierarchy: can only affect users with lower rank
    my_rank = get_user_rank(current_user)
    target_rank = get_user_rank(user)
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
    _: User = Depends(get_current_superadmin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_superadmin = True
    user.role = "admin"
    await db.flush()
    await db.refresh(user)
    return user


@router.patch("/{user_id}/promote", response_model=UserOut)
async def promote_user(
    user_id: str,
    role: str = Query(..., description="Target role: admin | workspace_admin | member"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_or_wsadmin),
):
    """
    Promote/demote a user to a specific global role.
    Hierarchy enforced: you can only set roles lower than your own.
    """
    if role not in ("admin", "workspace_admin", "member"):
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin', 'workspace_admin', or 'member'.")

    my_rank = get_user_rank(current_user)
    target_role_rank = ROLE_RANK.get(role, 1)

    # Only admins can promote to admin
    if target_role_rank >= my_rank:
        raise HTTPException(status_code=403, detail=f"You cannot assign the '{role}' role - it requires higher privileges.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Cannot demote someone of equal or higher rank
    existing_rank = get_user_rank(user)
    if existing_rank >= my_rank:
        raise HTTPException(status_code=403, detail="Cannot change role of a user with equal or higher role.")

    user.role = role
    user.is_superadmin = (role == "admin")

    await db.flush()
    await db.refresh(user)
    return user
