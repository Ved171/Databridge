from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_superadmin, get_current_admin_or_wsadmin, ROLE_RANK, get_user_rank
from app.models import User, ConnectorPermission, RLSPolicy, Connector
from app.schemas import PermissionUpsert, PermissionOut, RLSPolicyCreate, RLSPolicyUpdate, RLSPolicyOut

router = APIRouter()


# ─── CRUD Permission Matrix ───────────────────────────────────────────────────

@router.get("/connector/{connector_id}", response_model=List[PermissionOut])
async def get_connector_permissions(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    """List all user permissions for a connector (the tick-box matrix)."""
    result = await db.execute(
        select(ConnectorPermission).where(ConnectorPermission.connector_id == connector_id)
    )
    return result.scalars().all()


@router.put("/connector/{connector_id}", response_model=PermissionOut)
async def upsert_permission(
    connector_id: str,
    payload: PermissionUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_or_wsadmin),
):
    """
    Set or update CRUD permissions for a user on a connector.
    Hierarchy: cannot modify permissions of users with equal or higher role.
    """
    # Verify connector exists
    conn_result = await db.execute(select(Connector).where(Connector.id == connector_id))
    if not conn_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Connector not found")

    # Hierarchy check: cannot modify permissions of equal/higher role users
    target_result = await db.execute(select(User).where(User.id == payload.user_id))
    target_user = target_result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    my_rank = get_user_rank(current_user)
    target_rank = get_user_rank(target_user)
    if target_rank >= my_rank:
        raise HTTPException(status_code=403, detail="Cannot modify permissions of a user with equal or higher role")

    result = await db.execute(
        select(ConnectorPermission).where(
            ConnectorPermission.connector_id == connector_id,
            ConnectorPermission.user_id == payload.user_id,
        )
    )
    perm = result.scalar_one_or_none()

    if perm:
        perm.can_create = payload.can_create
        perm.can_read   = payload.can_read
        perm.can_update = payload.can_update
        perm.can_delete = payload.can_delete
        perm.granted_by = current_user.id
    else:
        perm = ConnectorPermission(
            connector_id=connector_id,
            user_id=payload.user_id,
            can_create=payload.can_create,
            can_read=payload.can_read,
            can_update=payload.can_update,
            can_delete=payload.can_delete,
            granted_by=current_user.id,
        )
        db.add(perm)

    await db.flush()
    await db.refresh(perm)
    return perm


@router.delete("/connector/{connector_id}/user/{user_id}")
async def revoke_permission(
    connector_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_or_wsadmin),
):
    """Completely revoke a user's access to a connector. Hierarchy enforced."""
    target_result = await db.execute(select(User).where(User.id == user_id))
    target_user = target_result.scalar_one_or_none()
    if target_user:
        my_rank = get_user_rank(current_user)
        target_rank = get_user_rank(target_user)
        if target_rank >= my_rank:
            raise HTTPException(status_code=403, detail="Cannot revoke permissions of a user with equal or higher role")

    await db.execute(
        delete(ConnectorPermission).where(
            ConnectorPermission.connector_id == connector_id,
            ConnectorPermission.user_id == user_id,
        )
    )
    return {"status": "revoked"}


@router.get("/my-permissions")
async def my_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current user's permissions across all connectors."""
    result = await db.execute(
        select(ConnectorPermission, Connector)
        .join(Connector, Connector.id == ConnectorPermission.connector_id)
        .where(ConnectorPermission.user_id == current_user.id)
    )
    rows = result.all()
    return [
        {
            "connector_id": p.connector_id,
            "connector_name": c.name,
            "connector_type": c.type,
            "can_create": p.can_create,
            "can_read": p.can_read,
            "can_update": p.can_update,
            "can_delete": p.can_delete,
        }
        for p, c in rows
    ]


# ─── RLS Policies ─────────────────────────────────────────────────────────────

@router.post("/connector/{connector_id}/rls", response_model=RLSPolicyOut)
async def create_rls_policy(
    connector_id: str,
    payload: RLSPolicyCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    policy = RLSPolicy(
        connector_id=connector_id,
        name=payload.name,
        table_name=payload.table_name,
        filter_expr=payload.filter_expr,
        applies_to_user_id=payload.applies_to_user_id,
        applies_to_role=payload.applies_to_role,
    )
    db.add(policy)
    await db.flush()
    await db.refresh(policy)
    return policy


@router.get("/connector/{connector_id}/rls", response_model=List[RLSPolicyOut])
async def list_rls_policies(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    result = await db.execute(
        select(RLSPolicy).where(RLSPolicy.connector_id == connector_id)
    )
    return result.scalars().all()


@router.patch("/connector/{connector_id}/rls/{policy_id}/toggle")
async def toggle_rls_policy(
    connector_id: str,
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    result = await db.execute(
        select(RLSPolicy).where(RLSPolicy.id == policy_id, RLSPolicy.connector_id == connector_id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    policy.is_active = not policy.is_active
    await db.flush()
    return {"id": policy.id, "is_active": policy.is_active}


@router.put("/connector/{connector_id}/rls/{policy_id}", response_model=RLSPolicyOut)
async def update_rls_policy(
    connector_id: str,
    policy_id: str,
    payload: RLSPolicyUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    result = await db.execute(
        select(RLSPolicy).where(RLSPolicy.id == policy_id, RLSPolicy.connector_id == connector_id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(policy, key, value)
    await db.flush()
    await db.refresh(policy)
    return policy


@router.delete("/connector/{connector_id}/rls/{policy_id}")
async def delete_rls_policy(
    connector_id: str,
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    result = await db.execute(
        select(RLSPolicy).where(RLSPolicy.id == policy_id, RLSPolicy.connector_id == connector_id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    await db.delete(policy)
    return {"status": "deleted"}
