"""
Scoped Manager Admin endpoints.

Allows managers with allow_share_access=True to grant/revoke direct
user-level connector and table permissions for their direct reports.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_user, is_grant_active
from app.models import (
    User, ConnectorPermission, TablePermission,
    UserManagerAssignment, Connector,
)

router = APIRouter()


# ── Pydantic payloads ─────────────────────────────────────────────────────────

class ConnectorAccessPayload(BaseModel):
    target_user_id: str
    can_read: bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False


class TableAccessPayload(BaseModel):
    target_user_id: str
    table_name: str
    can_read: bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False


class TableAccessDeletePayload(BaseModel):
    table_name: str


# ── Shared validation helpers ─────────────────────────────────────────────────

async def _require_share_access(
    caller: User, connector_id: str, db: AsyncSession
) -> ConnectorPermission:
    """Return the caller's ConnectorPermission if allow_share_access=True, else 403."""
    res = await db.execute(
        select(ConnectorPermission).where(
            ConnectorPermission.connector_id == connector_id,
            ConnectorPermission.user_id == str(caller.id),
        )
    )
    perm = res.scalar_one_or_none()
    if not perm or not is_grant_active(perm) or not perm.allow_share_access:
        raise HTTPException(status_code=403, detail="You do not have team access sharing permission for this connector.")
    return perm


async def _require_direct_report(caller_id: str, target_user_id: str, db: AsyncSession) -> None:
    """Verify target is a direct report of the caller."""
    res = await db.execute(
        select(UserManagerAssignment).where(
            UserManagerAssignment.manager_user_id == caller_id,
            UserManagerAssignment.member_user_id == target_user_id,
        )
    )
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Target user is not your direct report.")


def _check_not_escalating(caller_perm: ConnectorPermission, payload) -> None:
    """Verify caller is not granting permissions they don't have."""
    flags = ['can_read', 'can_create', 'can_update', 'can_delete']
    for flag in flags:
        if getattr(payload, flag, False) and not getattr(caller_perm, flag, False):
            raise HTTPException(
                status_code=400,
                detail="You cannot grant permissions you don't have."
            )


def _check_grantor_ownership(record, caller_id: str) -> None:
    """Check that the record was granted by the caller, else 403."""
    if record.granted_by_user_id is None or str(record.granted_by_user_id) != str(caller_id):
        raise HTTPException(
            status_code=403,
            detail="This user's access is managed at a higher level."
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/{connector_id}/scoped-admin/connector-access/")
async def grant_connector_access(
    connector_id: str,
    payload: ConnectorAccessPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Grant or update connector permission for a direct report."""
    # Validate connector exists
    connector = await db.get(Connector, connector_id)
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    # Rule: caller must have allow_share_access
    caller_perm = await _require_share_access(current_user, connector_id, db)

    # Rule: target must be direct report
    await _require_direct_report(str(current_user.id), payload.target_user_id, db)

    # Rule: cannot escalate
    _check_not_escalating(caller_perm, payload)

    # Check if target already has a permission record
    res = await db.execute(
        select(ConnectorPermission).where(
            ConnectorPermission.connector_id == connector_id,
            ConnectorPermission.user_id == payload.target_user_id,
        )
    )
    existing = res.scalar_one_or_none()

    if existing:
        # If exists but was not granted by caller, block
        if existing.granted_by_user_id is not None and str(existing.granted_by_user_id) != str(current_user.id):
            raise HTTPException(
                status_code=403,
                detail="This user's access is managed at a higher level."
            )
        if existing.granted_by_user_id is None:
            raise HTTPException(
                status_code=403,
                detail="This user's access is managed at a higher level."
            )
        existing.can_read = payload.can_read
        existing.can_create = payload.can_create
        existing.can_update = payload.can_update
        existing.can_delete = payload.can_delete
        existing.granted_by_user_id = str(current_user.id)
        existing.revoked_at = None
        existing.revoked_by = None
    else:
        perm = ConnectorPermission(
            connector_id=connector_id,
            user_id=payload.target_user_id,
            can_read=payload.can_read,
            can_create=payload.can_create,
            can_update=payload.can_update,
            can_delete=payload.can_delete,
            granted_by=str(current_user.id),
            granted_by_user_id=str(current_user.id),
        )
        db.add(perm)

    await db.flush()
    return {"status": "granted"}


@router.delete("/{connector_id}/scoped-admin/connector-access/{target_user_id}/")
async def revoke_connector_access(
    connector_id: str,
    target_user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke connector permission + cascade table permissions for a direct report."""
    await _require_share_access(current_user, connector_id, db)
    await _require_direct_report(str(current_user.id), target_user_id, db)

    # Find the permission record
    res = await db.execute(
        select(ConnectorPermission).where(
            ConnectorPermission.connector_id == connector_id,
            ConnectorPermission.user_id == target_user_id,
        )
    )
    existing = res.scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=404, detail="No connector permission found for this user.")

    _check_grantor_ownership(existing, str(current_user.id))

    # Cascade: delete table permissions granted by this caller for this connector+target
    await db.execute(
        delete(TablePermission).where(
            TablePermission.connector_id == connector_id,
            TablePermission.applies_to_user_id == target_user_id,
            TablePermission.granted_by_user_id == str(current_user.id),
        )
    )

    # Delete the connector permission
    await db.execute(
        delete(ConnectorPermission).where(
            ConnectorPermission.connector_id == connector_id,
            ConnectorPermission.user_id == target_user_id,
            ConnectorPermission.granted_by_user_id == str(current_user.id),
        )
    )

    await db.flush()
    return {"status": "revoked"}


@router.post("/{connector_id}/scoped-admin/table-access/")
async def grant_table_access(
    connector_id: str,
    payload: TableAccessPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Grant or update table permission for a direct report."""
    connector = await db.get(Connector, connector_id)
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    # Rule: caller must have allow_share_access
    caller_perm = await _require_share_access(current_user, connector_id, db)

    # Rule: target must be direct report
    await _require_direct_report(str(current_user.id), payload.target_user_id, db)

    # Rule: cannot escalate
    _check_not_escalating(caller_perm, payload)

    # Rule: caller must have access to this table themselves
    from app.core.deps import check_table_permission
    caller_has_table = await check_table_permission(
        connector_id, payload.table_name, 'read', current_user, db
    )
    if not caller_has_table:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this table yourself."
        )

    # Find existing table permission for this target+table
    res = await db.execute(
        select(TablePermission).where(
            TablePermission.connector_id == connector_id,
            TablePermission.applies_to_user_id == payload.target_user_id,
            TablePermission.table_name == payload.table_name,
        )
    )
    existing = res.scalar_one_or_none()

    if existing:
        if existing.granted_by_user_id is not None and str(existing.granted_by_user_id) != str(current_user.id):
            raise HTTPException(
                status_code=403,
                detail="This user's access is managed at a higher level."
            )
        if existing.granted_by_user_id is None:
            raise HTTPException(
                status_code=403,
                detail="This user's access is managed at a higher level."
            )
        existing.can_read = payload.can_read
        existing.can_create = payload.can_create
        existing.can_update = payload.can_update
        existing.can_delete = payload.can_delete
        existing.granted_by_user_id = str(current_user.id)
    else:
        tp = TablePermission(
            connector_id=connector_id,
            table_name=payload.table_name,
            applies_to_user_id=payload.target_user_id,
            can_read=payload.can_read,
            can_create=payload.can_create,
            can_update=payload.can_update,
            can_delete=payload.can_delete,
            granted_by_user_id=str(current_user.id),
        )
        db.add(tp)

    await db.flush()
    return {"status": "granted"}


from typing import List


class TableAccessBulkDeletePayload(BaseModel):
    table_names: List[str]


@router.post("/{connector_id}/scoped-admin/table-access/{target_user_id}/bulk-revoke")
async def bulk_revoke_table_access(
    connector_id: str,
    target_user_id: str,
    payload: TableAccessBulkDeletePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke multiple table permissions for a direct report."""
    await _require_share_access(current_user, connector_id, db)
    await _require_direct_report(str(current_user.id), target_user_id, db)

    for table_name in payload.table_names:
        res = await db.execute(
            select(TablePermission).where(
                TablePermission.connector_id == connector_id,
                TablePermission.applies_to_user_id == target_user_id,
                TablePermission.table_name == table_name,
            )
        )
        existing = res.scalar_one_or_none()
        if existing:
            _check_grantor_ownership(existing, str(current_user.id))
            await db.delete(existing)
            
    await db.commit()
    return {"status": "revoked"}


@router.delete("/{connector_id}/scoped-admin/table-access/{target_user_id}/")
async def revoke_table_access(
    connector_id: str,
    target_user_id: str,
    payload: TableAccessDeletePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke a single table permission for a direct report."""
    await _require_share_access(current_user, connector_id, db)
    await _require_direct_report(str(current_user.id), target_user_id, db)

    res = await db.execute(
        select(TablePermission).where(
            TablePermission.connector_id == connector_id,
            TablePermission.applies_to_user_id == target_user_id,
            TablePermission.table_name == payload.table_name,
        )
    )
    existing = res.scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=404, detail="No table permission found.")

    _check_grantor_ownership(existing, str(current_user.id))

    await db.execute(
        delete(TablePermission).where(
            TablePermission.id == existing.id,
        )
    )

    await db.flush()
    return {"status": "revoked"}


@router.get("/{connector_id}/scoped-admin/reports/")
async def list_reports(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List direct reports with their permissions for this connector."""
    # Verify caller has share access
    await _require_share_access(current_user, connector_id, db)

    # Get direct reports
    res = await db.execute(
        select(UserManagerAssignment.member_user_id).where(
            UserManagerAssignment.manager_user_id == str(current_user.id),
        )
    )
    report_ids = [str(r) for r in res.scalars().all()]

    if not report_ids:
        return []

    # Fetch user details
    users_res = await db.execute(
        select(User).where(User.id.in_(report_ids), User.is_active == True)
    )
    report_users = users_res.scalars().all()

    # Fetch connector permissions for these users
    conn_perms_res = await db.execute(
        select(ConnectorPermission).where(
            ConnectorPermission.connector_id == connector_id,
            ConnectorPermission.user_id.in_(report_ids),
        )
    )
    conn_perms = {str(p.user_id): p for p in conn_perms_res.scalars().all()}

    # Fetch table permissions for these users
    table_perms_res = await db.execute(
        select(TablePermission).where(
            TablePermission.connector_id == connector_id,
            TablePermission.applies_to_user_id.in_(report_ids),
        )
    )
    table_perms_by_user: dict[str, list] = {}
    for tp in table_perms_res.scalars().all():
        uid = str(tp.applies_to_user_id)
        if uid not in table_perms_by_user:
            table_perms_by_user[uid] = []
        table_perms_by_user[uid].append(tp)

    result = []
    for u in report_users:
        uid = str(u.id)
        cp = conn_perms.get(uid)
        connector_permission = None
        if cp and is_grant_active(cp):
            connector_permission = {
                "can_read": cp.can_read,
                "can_create": cp.can_create,
                "can_update": cp.can_update,
                "can_delete": cp.can_delete,
                "granted_by_caller": str(cp.granted_by_user_id) == str(current_user.id) if cp.granted_by_user_id else False,
            }

        tps = table_perms_by_user.get(uid, [])
        table_permissions = [
            {
                "table_name": tp.table_name,
                "can_read": tp.can_read,
                "can_create": tp.can_create,
                "can_update": tp.can_update,
                "can_delete": tp.can_delete,
                "granted_by_caller": str(tp.granted_by_user_id) == str(current_user.id) if tp.granted_by_user_id else False,
            }
            for tp in tps
        ]

        result.append({
            "user_id": uid,
            "full_name": u.name,
            "email": u.email,
            "connector_permission": connector_permission,
            "table_permissions": table_permissions,
        })

    return result
