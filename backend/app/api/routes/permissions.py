from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.deps import (
    get_current_user, get_current_superadmin, get_current_admin_or_wsadmin,
    ROLE_RANK, get_user_rank,
    resolve_department_chain, resolve_managed_users,
    check_table_permission, check_connector_permission, is_grant_active,
)
from app.services.schema_cache import invalidate_connector_schema
from app.models import (
    User, ConnectorPermission, RLSPolicy, Connector, TablePermission, 
    TablePermissionDepartment, TablePermissionRole,
    ConnectorPermissionDepartment, ConnectorPermissionRole
)
from app.schemas import (
    PermissionUpsert, PermissionOut, RLSPolicyCreate, RLSPolicyUpdate, RLSPolicyOut,
    TablePermissionCreate, TablePermissionOut, DeptPermissionEntry, RolePermissionEntry,
    ConnectorPermissionBulkUpdate, ConnectorPermissionOut
)


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
        select(ConnectorPermission).where(
            ConnectorPermission.connector_id == connector_id,
            ConnectorPermission.user_id.is_not(None)
        )
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
    connector = conn_result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")


    # Hierarchy check: cannot modify permissions of equal/higher role users
    target_result = await db.execute(select(User).where(User.id == payload.user_id))
    target_user = target_result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    my_rank = await get_user_rank(current_user, db)
    target_rank = await get_user_rank(target_user, db)
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
        perm.allow_share_access = payload.allow_share_access
        perm.granted_by = current_user.id
        perm.valid_from = to_naive_utc(payload.valid_from)
        perm.expires_at = to_naive_utc(payload.expires_at)
        perm.grant_reason = payload.grant_reason
        perm.revoked_at = None
        perm.revoked_by = None
    else:
        perm = ConnectorPermission(
            connector_id=connector_id,
            user_id=payload.user_id,
            can_create=payload.can_create,
            can_read=payload.can_read,
            can_update=payload.can_update,
            can_delete=payload.can_delete,
            allow_share_access=payload.allow_share_access,
            granted_by=current_user.id,
            valid_from=to_naive_utc(payload.valid_from),
            expires_at=to_naive_utc(payload.expires_at),
            grant_reason=payload.grant_reason,
        )
        db.add(perm)

    # Create notification for target user
    from app.models import Notification
    expires_str = f"until {payload.expires_at.strftime('%Y-%m-%d %H:%M:%S')}" if payload.expires_at else "permanently"
    notif = Notification(
        user_id=payload.user_id,
        title="Access Granted",
        message=f"You have been granted {expires_str} access to connector '{connector.name}'.",
        is_read=False,
    )
    db.add(notif)

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
        my_rank = await get_user_rank(current_user, db)
        target_rank = await get_user_rank(target_user, db)
        if target_rank >= my_rank:
            raise HTTPException(status_code=403, detail="Cannot revoke permissions of a user with equal or higher role")

    await db.execute(
        delete(ConnectorPermission).where(
            ConnectorPermission.connector_id == connector_id,
            ConnectorPermission.user_id == user_id,
        )
    )

    # Auto-revoke: cascade-delete permissions this user granted to their reports
    await db.execute(
        delete(ConnectorPermission).where(
            ConnectorPermission.granted_by_user_id == user_id,
            ConnectorPermission.connector_id == connector_id,
        )
    )
    await db.execute(
        delete(TablePermission).where(
            TablePermission.granted_by_user_id == user_id,
            TablePermission.connector_id == connector_id,
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
            "allow_share_access": p.allow_share_access,
            "expires_at": p.expires_at,
            "valid_from": p.valid_from,
            "is_active": is_grant_active(p),
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
    # Fetch connector to determine connector type and check if it exists
    conn_result = await db.execute(select(Connector).where(Connector.id == connector_id))
    connector = conn_result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    db_type = (connector.type.value if hasattr(connector.type, "value") else str(connector.type)).split(".")[-1].lower()
    nosql_types = {"mongodb", "elasticsearch", "redis", "salesforce"}

    if db_type in nosql_types:
        if not payload.filter_expr_nosql:
            raise HTTPException(
                status_code=400,
                detail=f"RLS policy on {db_type} connector requires filter_expr_nosql (JSON structure)."
            )
        if db_type == "redis":
            if not isinstance(payload.filter_expr_nosql, dict) or "key_pattern" not in payload.filter_expr_nosql:
                raise HTTPException(
                    status_code=400,
                    detail="Redis RLS policy requires a JSON object with 'key_pattern' (e.g. {'key_pattern': 'user:{user.id}:*'})"
                )
    else:
        if not payload.filter_expr:
            raise HTTPException(
                status_code=400,
                detail=f"RLS policy on SQL connector {db_type} requires filter_expr (SQL fragment)."
            )

    policy = RLSPolicy(
        connector_id=connector_id,
        name=payload.name,
        table_name=payload.table_name,
        filter_expr=payload.filter_expr,
        filter_expr_nosql=payload.filter_expr_nosql,
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

    conn_result = await db.execute(select(Connector).where(Connector.id == connector_id))
    connector = conn_result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    db_type = (connector.type.value if hasattr(connector.type, "value") else str(connector.type)).split(".")[-1].lower()
    nosql_types = {"mongodb", "elasticsearch", "redis", "salesforce"}

    filter_expr = payload.filter_expr if payload.filter_expr is not None else policy.filter_expr
    filter_expr_nosql = payload.filter_expr_nosql if payload.filter_expr_nosql is not None else policy.filter_expr_nosql

    if db_type in nosql_types:
        if not filter_expr_nosql:
            raise HTTPException(
                status_code=400,
                detail=f"RLS policy on {db_type} connector requires filter_expr_nosql (JSON structure)."
            )
        if db_type == "redis":
            if not isinstance(filter_expr_nosql, dict) or "key_pattern" not in filter_expr_nosql:
                raise HTTPException(
                    status_code=400,
                    detail="Redis RLS policy requires a JSON object with 'key_pattern'"
                )
    else:
        if not filter_expr:
            raise HTTPException(
                status_code=400,
                detail=f"RLS policy on SQL connector {db_type} requires filter_expr (SQL fragment)."
            )

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


# ─── Table Permissions ────────────────────────────────────────────────────────

@router.get("/connector/{connector_id}/tables", response_model=List[TablePermissionOut])
async def list_table_permissions(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    """List all table permissions for a connector (legacy compatibility)."""
    result = await db.execute(
        select(TablePermission)
        .options(selectinload(TablePermission.departments), selectinload(TablePermission.roles))
        .where(TablePermission.connector_id == connector_id)
    )
    return result.scalars().all()


@router.post("/connector/{connector_id}/tables", response_model=TablePermissionOut)
async def create_table_permission_legacy(
    connector_id: str,
    payload: TablePermissionCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    """Create a new table permission rule (legacy compatibility)."""
    payload.connector_id = connector_id
    return await create_table_permission_rule(payload, db)


@router.delete("/connector/{connector_id}/tables/{permission_id}")
async def delete_table_permission_legacy(
    connector_id: str,
    permission_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    """Delete a table permission rule (legacy compatibility)."""
    return await delete_table_permission_rule(permission_id, db)


@router.get("/tables/", response_model=List[TablePermissionOut])
async def list_all_table_permissions(
    connector_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    stmt = select(TablePermission).options(
        selectinload(TablePermission.departments),
        selectinload(TablePermission.roles)
    )
    if connector_id:
        stmt = stmt.where(TablePermission.connector_id == connector_id)
    result = await db.execute(stmt)
    db_perms = list(result.scalars().all())

    # Fetch package table rules!
    from app.models import PackageTableRule, PackageDepartmentAssignment, PackageRoleAssignment, AccessPackage
    from app.core.deps import is_grant_active
    
    pkg_stmt = select(PackageTableRule, AccessPackage).join(AccessPackage, AccessPackage.id == PackageTableRule.package_id)
    if connector_id:
        pkg_stmt = pkg_stmt.where(PackageTableRule.connector_id == connector_id)
    pkg_res = await db.execute(pkg_stmt)
    pkg_rules = pkg_res.all()
    
    virtual_perms = []
    for rule, pkg in pkg_rules:
        # Fetch department and role assignments for this package
        dept_assign_res = await db.execute(
            select(PackageDepartmentAssignment).where(PackageDepartmentAssignment.package_id == pkg.id)
        )
        dept_assigns = dept_assign_res.scalars().all()
        
        role_assign_res = await db.execute(
            select(PackageRoleAssignment).where(PackageRoleAssignment.package_id == pkg.id)
        )
        role_assigns = role_assign_res.scalars().all()
        
        # Construct DeptPermissionEntry objects
        depts = [
            DeptPermissionEntry(
                id=da.id,
                department_id=da.department_id,
                role_id=da.role_id,
                is_deny=rule.is_deny,
                can_read=rule.can_read,
                can_create=rule.can_create,
                can_update=rule.can_update,
                can_delete=rule.can_delete,
                grant_reason=f"Via Package: {pkg.name}",
            )
            for da in dept_assigns
            if is_grant_active(da)
        ]
        
        roles = [
            RolePermissionEntry(
                id=ra.id,
                role_id=ra.role_id,
                is_deny=rule.is_deny,
                can_read=rule.can_read,
                can_create=rule.can_create,
                can_update=rule.can_update,
                can_delete=rule.can_delete,
                grant_reason=f"Via Package: {pkg.name}",
            )
            for ra in role_assigns
            if is_grant_active(ra)
        ]
        
        # Only add if it actually applies to some department or role
        if depts or roles:
            virtual_perms.append({
                "id": str(rule.id),
                "connector_id": str(rule.connector_id),
                "table_name": f"{rule.table_name} (Package: {pkg.name})",
                "applies_to_user_id": None,
                "can_read": rule.can_read,
                "can_create": rule.can_create,
                "can_update": rule.can_update,
                "can_delete": rule.can_delete,
                "created_at": pkg.created_at,
                "departments": depts,
                "roles": roles,
                "is_package_rule": True,
            })
            
    return db_perms + virtual_perms


@router.post("/tables/", response_model=TablePermissionOut, status_code=201)
async def create_table_permission_rule(
    payload: TablePermissionCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    # Verify connector exists
    conn_result = await db.execute(select(Connector).where(Connector.id == payload.connector_id))
    connector = conn_result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    # If user_id is provided, verify it exists
    if payload.applies_to_user_id:
        user_res = await db.execute(select(User).where(User.id == payload.applies_to_user_id))
        if not user_res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Target user not found")

    # Create TablePermission
    perm = TablePermission(
        connector_id=payload.connector_id,
        table_name=payload.table_name,
        applies_to_user_id=payload.applies_to_user_id,
        can_read=payload.can_read,
        can_create=payload.can_create,
        can_update=payload.can_update,
        can_delete=payload.can_delete,
    )
    db.add(perm)
    await db.flush()

    # Bulk insert departments
    for dept_entry in payload.departments:
        dept_perm = TablePermissionDepartment(
            table_permission_id=perm.id,
            department_id=dept_entry.department_id,
            role_id=dept_entry.role_id,
            is_deny=dept_entry.is_deny,
            can_read=dept_entry.can_read,
            can_create=dept_entry.can_create,
            can_update=dept_entry.can_update,
            can_delete=dept_entry.can_delete,
        )
        db.add(dept_perm)

    # Bulk insert roles
    for role_entry in payload.roles:
        role_perm = TablePermissionRole(
            table_permission_id=perm.id,
            role_id=role_entry.role_id,
            is_deny=role_entry.is_deny,
            can_read=role_entry.can_read,
            can_create=role_entry.can_create,
            can_update=role_entry.can_update,
            can_delete=role_entry.can_delete,
        )
        db.add(role_perm)

    await db.commit()
    invalidate_connector_schema()

    # Re-load with options
    stmt = select(TablePermission).options(
        selectinload(TablePermission.departments),
        selectinload(TablePermission.roles)
    ).where(TablePermission.id == perm.id)
    res = await db.execute(stmt)
    return res.scalar_one()


@router.patch("/tables/{permission_id}", response_model=TablePermissionOut)
async def update_table_permission_rule(
    permission_id: str,
    payload: TablePermissionCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    stmt = select(TablePermission).options(
        selectinload(TablePermission.departments),
        selectinload(TablePermission.roles)
    ).where(TablePermission.id == permission_id)
    res = await db.execute(stmt)
    perm = res.scalar_one_or_none()
    if not perm:
        raise HTTPException(status_code=404, detail="Table permission not found")

    # Update parent fields
    perm.table_name = payload.table_name
    perm.applies_to_user_id = payload.applies_to_user_id
    perm.can_read = payload.can_read
    perm.can_create = payload.can_create
    perm.can_update = payload.can_update
    perm.can_delete = payload.can_delete

    # Replace strategy for departments
    await db.execute(delete(TablePermissionDepartment).where(TablePermissionDepartment.table_permission_id == perm.id))
    for dept_entry in payload.departments:
        dept_perm = TablePermissionDepartment(
            table_permission_id=perm.id,
            department_id=dept_entry.department_id,
            role_id=dept_entry.role_id,
            is_deny=dept_entry.is_deny,
            can_read=dept_entry.can_read,
            can_create=dept_entry.can_create,
            can_update=dept_entry.can_update,
            can_delete=dept_entry.can_delete,
        )
        db.add(dept_perm)

    # Replace strategy for roles
    await db.execute(delete(TablePermissionRole).where(TablePermissionRole.table_permission_id == perm.id))
    for role_entry in payload.roles:
        role_perm = TablePermissionRole(
            table_permission_id=perm.id,
            role_id=role_entry.role_id,
            is_deny=role_entry.is_deny,
            can_read=role_entry.can_read,
            can_create=role_entry.can_create,
            can_update=role_entry.can_update,
            can_delete=role_entry.can_delete,
        )
        db.add(role_perm)

    await db.commit()
    invalidate_connector_schema()

    # Re-fetch
    stmt = select(TablePermission).options(
        selectinload(TablePermission.departments),
        selectinload(TablePermission.roles)
    ).where(TablePermission.id == perm.id)
    res = await db.execute(stmt)
    return res.scalar_one()


from pydantic import BaseModel


class BulkDeleteTablesPayload(BaseModel):
    ids: List[str]


@router.post("/tables/bulk-delete")
async def bulk_delete_table_permissions(
    payload: BulkDeleteTablesPayload,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    import uuid
    for perm_id in payload.ids:
        stmt = select(TablePermission).where(TablePermission.id == uuid.UUID(perm_id))
        res = await db.execute(stmt)
        perm = res.scalar_one_or_none()
        if perm:
            await db.delete(perm)
    await db.commit()
    return {"status": "deleted", "message": f"Successfully deleted {len(payload.ids)} table permissions."}


@router.delete("/tables/{permission_id}")
async def delete_table_permission_rule(
    permission_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    stmt = select(TablePermission).where(TablePermission.id == permission_id)
    res = await db.execute(stmt)
    perm = res.scalar_one_or_none()
    if not perm:
        raise HTTPException(status_code=404, detail="Table permission not found")
    await db.delete(perm)
    await db.commit()
    invalidate_connector_schema()
    return {"status": "deleted"}


@router.post("/tables/{permission_id}/departments", response_model=TablePermissionOut)
async def bulk_add_department_grants(
    permission_id: str,
    departments_payload: List[DeptPermissionEntry],
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    stmt = select(TablePermission).where(TablePermission.id == permission_id)
    res = await db.execute(stmt)
    perm = res.scalar_one_or_none()
    if not perm:
        raise HTTPException(status_code=404, detail="Table permission not found")

    for dept_entry in departments_payload:
        # Check if already exists, update or insert
        check_stmt = select(TablePermissionDepartment).where(
            TablePermissionDepartment.table_permission_id == perm.id,
            TablePermissionDepartment.department_id == dept_entry.department_id
        )
        if dept_entry.role_id:
            check_stmt = check_stmt.where(TablePermissionDepartment.role_id == dept_entry.role_id)
        else:
            check_stmt = check_stmt.where(TablePermissionDepartment.role_id.is_(None))
        check_res = await db.execute(check_stmt)
        existing = check_res.scalar_one_or_none()
        if existing:
            existing.is_deny = dept_entry.is_deny
            existing.can_read = dept_entry.can_read
            existing.can_create = dept_entry.can_create
            existing.can_update = dept_entry.can_update
            existing.can_delete = dept_entry.can_delete
        else:
            new_dept = TablePermissionDepartment(
                table_permission_id=perm.id,
                department_id=dept_entry.department_id,
                role_id=dept_entry.role_id,
                is_deny=dept_entry.is_deny,
                can_read=dept_entry.can_read,
                can_create=dept_entry.can_create,
                can_update=dept_entry.can_update,
                can_delete=dept_entry.can_delete,
            )
            db.add(new_dept)

    await db.commit()

    # Re-fetch
    stmt = select(TablePermission).options(
        selectinload(TablePermission.departments),
        selectinload(TablePermission.roles)
    ).where(TablePermission.id == perm.id)
    res = await db.execute(stmt)
    return res.scalar_one()


@router.post("/tables/{permission_id}/roles", response_model=TablePermissionOut)
async def bulk_add_role_grants(
    permission_id: str,
    roles_payload: List[RolePermissionEntry],
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    stmt = select(TablePermission).where(TablePermission.id == permission_id)
    res = await db.execute(stmt)
    perm = res.scalar_one_or_none()
    if not perm:
        raise HTTPException(status_code=404, detail="Table permission not found")

    for role_entry in roles_payload:
        # Check if already exists, update or insert
        check_stmt = select(TablePermissionRole).where(
            TablePermissionRole.table_permission_id == perm.id,
            TablePermissionRole.role_id == role_entry.role_id
        )
        check_res = await db.execute(check_stmt)
        existing = check_res.scalar_one_or_none()
        if existing:
            existing.is_deny = role_entry.is_deny
            existing.can_read = role_entry.can_read
            existing.can_create = role_entry.can_create
            existing.can_update = role_entry.can_update
            existing.can_delete = role_entry.can_delete
        else:
            new_role = TablePermissionRole(
                table_permission_id=perm.id,
                role_id=role_entry.role_id,
                is_deny=role_entry.is_deny,
                can_read=role_entry.can_read,
                can_create=role_entry.can_create,
                can_update=role_entry.can_update,
                can_delete=role_entry.can_delete,
            )
            db.add(new_role)

    await db.commit()

    # Re-fetch
    stmt = select(TablePermission).options(
        selectinload(TablePermission.departments),
        selectinload(TablePermission.roles)
    ).where(TablePermission.id == perm.id)
    res = await db.execute(stmt)
    return res.scalar_one()


@router.delete("/tables/{permission_id}/departments/{dept_id}")
async def delete_department_grant(
    permission_id: str,
    dept_id: str,
    role_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    stmt = delete(TablePermissionDepartment).where(
        TablePermissionDepartment.table_permission_id == permission_id,
        TablePermissionDepartment.department_id == dept_id
    )
    if role_id:
        stmt = stmt.where(TablePermissionDepartment.role_id == role_id)
    else:
        stmt = stmt.where(TablePermissionDepartment.role_id.is_(None))
    await db.execute(stmt)
    await db.commit()
    return {"status": "deleted"}


@router.delete("/tables/{permission_id}/roles/{role_id}")
async def delete_role_grant(
    permission_id: str,
    role_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    await db.execute(
        delete(TablePermissionRole).where(
            TablePermissionRole.table_permission_id == permission_id,
            TablePermissionRole.role_id == role_id
        )
    )
    await db.commit()
    return {"status": "deleted"}


# ─── Connector-Level Permissions ──────────────────────────────────────────────

def to_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        import datetime as dt_module
        return dt.astimezone(dt_module.timezone.utc).replace(tzinfo=None)
    return dt


def parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        cleaned = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return to_naive_utc(dt)
    except Exception:
        return None


@router.get("/connector/{connector_id}/grants")
async def get_connector_permission_grants(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    """
    Get connector-level permissions grouped by user, department, and role.
    Returns active dept/role junction rows for the connector.
    """
    # Fetch the parent connector_permission records (user-level)
    perm_result = await db.execute(
        select(ConnectorPermission).where(
            ConnectorPermission.connector_id == connector_id
        )
    )
    
    user_perms = perm_result.scalars().all()
    user_grants = [
        {
            "id": p.id,
            "user_id": p.user_id,
            "can_read": p.can_read,
            "can_create": p.can_create,
            "can_update": p.can_update,
            "can_delete": p.can_delete,
            "valid_from": p.valid_from,
            "expires_at": p.expires_at,
            "revoked_at": p.revoked_at,
            "revoked_by": p.revoked_by,
            "grant_reason": p.grant_reason,
            "is_active": is_grant_active(p),
        }
        for p in user_perms
        if p.user_id is not None
    ]

    # Fetch department junction rows using explicit join
    dept_res = await db.execute(
        select(ConnectorPermissionDepartment)
        .join(ConnectorPermission, 
              ConnectorPermissionDepartment.connector_permission_id == ConnectorPermission.id)
        .where(ConnectorPermission.connector_id == connector_id)
    )
    dept_grants = [
        {
            "id": str(d.id),
            "department_id": str(d.department_id),
            "role_id": str(d.role_id) if d.role_id else None,
            "is_deny": d.is_deny,
            "can_read": d.can_read,
            "can_create": d.can_create,
            "can_update": d.can_update,
            "can_delete": d.can_delete,
            "valid_from": d.valid_from,
            "expires_at": d.expires_at,
            "revoked_at": d.revoked_at,
            "revoked_by": d.revoked_by,
            "grant_reason": d.grant_reason,
            "is_active": is_grant_active(d),
        }
        for d in dept_res.scalars().all()
    ]

    # Fetch role junction rows using explicit join
    role_res = await db.execute(
        select(ConnectorPermissionRole)
        .join(ConnectorPermission,
              ConnectorPermissionRole.connector_permission_id == ConnectorPermission.id)
        .where(ConnectorPermission.connector_id == connector_id)
    )
    role_grants = [
        {
            "id": str(r.id),
            "role_id": str(r.role_id),
            "is_deny": r.is_deny,
            "can_read": r.can_read,
            "can_create": r.can_create,
            "can_update": r.can_update,
            "can_delete": r.can_delete,
            "valid_from": r.valid_from,
            "expires_at": r.expires_at,
            "revoked_at": r.revoked_at,
            "revoked_by": r.revoked_by,
            "grant_reason": r.grant_reason,
            "is_active": is_grant_active(r),
        }
        for r in role_res.scalars().all()
    ]

    return {
        "connector_id": connector_id,
        "user_grants": user_grants,
        "department_grants": dept_grants,
        "role_grants": role_grants,
    }


@router.post("/connector/{connector_id}/grants/bulk")
async def bulk_update_connector_grants(
    connector_id: str,
    payload: dict,  # { "departments": [...], "roles": [...] }
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    """
    Bulk update connector-level department and role permissions.
    Uses replace strategy: delete all existing, then re-insert from payload.
    """
    from app.models import ConnectorPermissionDepartment, ConnectorPermissionRole
    from uuid import uuid4

    # Verify connector exists
    conn_result = await db.execute(select(Connector).where(Connector.id == connector_id))
    if not conn_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Connector not found")

    # Get or create the reference connector_permission (represents the connector itself)
    perm_result = await db.execute(
        select(ConnectorPermission)
        .where(
            ConnectorPermission.connector_id == connector_id,
            ConnectorPermission.user_id == None  # sentinel for connector-level grants
        )
    )
    ref_perm = perm_result.scalar_one_or_none()

    if not ref_perm:
        ref_perm = ConnectorPermission(
            id=uuid4(),
            connector_id=connector_id,
            user_id=None,
            can_read=True,
            can_create=False,
            can_update=False,
            can_delete=False,
        )
        db.add(ref_perm)
        await db.flush()

    # Delete existing department and role grants
    await db.execute(
        delete(ConnectorPermissionDepartment).where(
            ConnectorPermissionDepartment.connector_permission_id == ref_perm.id
        )
    )
    await db.execute(
        delete(ConnectorPermissionRole).where(
            ConnectorPermissionRole.connector_permission_id == ref_perm.id
        )
    )

    # Insert new department grants
    departments = payload.get("departments", [])
    for dept_entry in departments:
        dept_perm = ConnectorPermissionDepartment(
            id=uuid4(),
            connector_permission_id=ref_perm.id,
            department_id=dept_entry.get("department_id"),
            role_id=dept_entry.get("role_id"),
            is_deny=dept_entry.get("is_deny", False),
            can_read=dept_entry.get("can_read", True),
            can_create=dept_entry.get("can_create", False),
            can_update=dept_entry.get("can_update", False),
            can_delete=dept_entry.get("can_delete", False),
            valid_from=parse_dt(dept_entry.get("valid_from")),
            expires_at=parse_dt(dept_entry.get("expires_at")),
            revoked_at=parse_dt(dept_entry.get("revoked_at")),
            revoked_by=dept_entry.get("revoked_by"),
            grant_reason=dept_entry.get("grant_reason"),
        )
        db.add(dept_perm)

    # Insert new role grants
    roles = payload.get("roles", [])
    for role_entry in roles:
        role_perm = ConnectorPermissionRole(
            id=uuid4(),
            connector_permission_id=ref_perm.id,
            role_id=role_entry.get("role_id"),
            is_deny=role_entry.get("is_deny", False),
            can_read=role_entry.get("can_read", True),
            can_create=role_entry.get("can_create", False),
            can_update=role_entry.get("can_update", False),
            can_delete=role_entry.get("can_delete", False),
            valid_from=parse_dt(role_entry.get("valid_from")),
            expires_at=parse_dt(role_entry.get("expires_at")),
            revoked_at=parse_dt(role_entry.get("revoked_at")),
            revoked_by=role_entry.get("revoked_by"),
            grant_reason=role_entry.get("grant_reason"),
        )
        db.add(role_perm)

    await db.commit()

    # Return the updated state
    return await get_connector_permission_grants(connector_id, db, _)


@router.delete("/connector/{connector_id}/grants/departments/{dept_id}")
async def delete_connector_department_grant(
    connector_id: str,
    dept_id: str,
    role_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    """Delete a department's grant for a connector."""
    # Get the connector's reference permission first
    perm_result = await db.execute(
        select(ConnectorPermission).where(
            ConnectorPermission.connector_id == connector_id,
            ConnectorPermission.user_id == None
        )
    )
    ref_perm = perm_result.scalar_one_or_none()
    
    if ref_perm:
        stmt = delete(ConnectorPermissionDepartment).where(
            ConnectorPermissionDepartment.connector_permission_id == ref_perm.id,
            ConnectorPermissionDepartment.department_id == dept_id
        )
        if role_id:
            stmt = stmt.where(ConnectorPermissionDepartment.role_id == role_id)
        else:
            stmt = stmt.where(ConnectorPermissionDepartment.role_id.is_(None))
        await db.execute(stmt)
        await db.commit()
    
    return {"status": "deleted"}


@router.delete("/connector/{connector_id}/grants/roles/{role_id}")
async def delete_connector_role_grant(
    connector_id: str,
    role_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    """Delete a role's grant for a connector."""
    # Get the connector's reference permission first
    perm_result = await db.execute(
        select(ConnectorPermission).where(
            ConnectorPermission.connector_id == connector_id,
            ConnectorPermission.user_id == None
        )
    )
    ref_perm = perm_result.scalar_one_or_none()
    
    if ref_perm:
        await db.execute(
            delete(ConnectorPermissionRole).where(
                ConnectorPermissionRole.connector_permission_id == ref_perm.id,
                ConnectorPermissionRole.role_id == role_id
            )
        )
        await db.commit()
    
    return {"status": "deleted"}


# ─── Permission Debug ────────────────────────────────────────────────────────

@router.get("/debug")
async def debug_permission(
    user_id: str,
    connector_id: str,
    table_name: Optional[str] = None,
    table_names: Optional[str] = None,
    operation: str = "read",
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    """
    Superadmin-only endpoint to trace exactly why a user has or does not have access.
    Resolves full role chain, department chain, and managed users for debugging.
    Supports single or multiple tables.
    """
    from app.models import Role, Department

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Build request-scoped cache
    cache: dict = {}

    role_chain = [str(user.role_id)] if user.role_id else []
    dept_chain = await resolve_department_chain(user.department_id, db, _cache=cache)
    managed_users = await resolve_managed_users(str(user.id), db)

    # Resolve role and dept names for readability
    roles_result = await db.execute(select(Role).where(Role.id.in_(role_chain))) if role_chain else None
    depts_result = await db.execute(select(Department).where(Department.id.in_(dept_chain))) if dept_chain else None

    role_objs = list(roles_result.scalars()) if roles_result else []
    dept_objs = list(depts_result.scalars()) if depts_result else []

    # Order role/dept objects by their position in the chain
    role_id_to_obj = {str(r.id): r for r in role_objs}
    dept_id_to_obj = {str(d.id): d for d in dept_objs}
    ordered_roles = [role_id_to_obj[rid] for rid in role_chain if rid in role_id_to_obj]
    ordered_depts = [dept_id_to_obj[did] for did in dept_chain if did in dept_id_to_obj]

    decisions = {}
    tables = []
    if table_names:
        tables = [t.strip() for t in table_names.split(",") if t.strip()]
    elif table_name:
        tables = [table_name]

    if tables:
        for t in tables:
            result = await check_table_permission(connector_id, t, operation, user, db, _cache=cache)
            decisions[t] = "allow" if result else "deny"
        overall_decision = "allow" if all(decisions[t] == "allow" for t in tables) else "deny"
    else:
        result = await check_connector_permission(connector_id, operation, user, db, _cache=cache)
        overall_decision = "allow" if result else "deny"

    return {
        "user_id": user_id,
        "connector_id": connector_id,
        "table_name": table_name,
        "table_names": tables,
        "operation": operation,
        "decision": overall_decision,
        "decisions": decisions,
        "role_chain": [{"id": str(r.id), "name": r.name, "level": r.level} for r in ordered_roles],
        "dept_chain": [{"id": str(d.id), "name": d.name} for d in ordered_depts],
        "managed_user_count": len(managed_users),
    }


@router.post('/connector/{permission_id}/revoke')
async def revoke_connector_permission(
    permission_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin)
):
    perm = await db.get(ConnectorPermission, permission_id)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission grant not found.")
    if perm.revoked_at:
        raise HTTPException(status_code=409, detail="Grant is already revoked.")

    perm.revoked_at = datetime.utcnow()
    perm.revoked_by = current_user.id
    await db.commit()
    return {"message": "Grant revoked.", "revoked_at": perm.revoked_at}


@router.post('/connector/dept/{junction_id}/revoke')
async def revoke_connector_dept_permission(
    junction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin)
):
    import uuid
    try:
        j_uuid = uuid.UUID(junction_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid junction UUID format.")

    perm = await db.get(ConnectorPermissionDepartment, j_uuid)
    if not perm:
        raise HTTPException(status_code=404, detail="Department permission grant not found.")
    if perm.revoked_at:
        raise HTTPException(status_code=409, detail="Grant is already revoked.")

    perm.revoked_at = datetime.utcnow()
    perm.revoked_by = current_user.id
    await db.commit()
    return {"message": "Grant revoked.", "revoked_at": perm.revoked_at}


@router.post('/connector/role/{junction_id}/revoke')
async def revoke_connector_role_permission(
    junction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin)
):
    import uuid
    try:
        j_uuid = uuid.UUID(junction_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid junction UUID format.")

    perm = await db.get(ConnectorPermissionRole, j_uuid)
    if not perm:
        raise HTTPException(status_code=404, detail="Role permission grant not found.")
    if perm.revoked_at:
        raise HTTPException(status_code=409, detail="Grant is already revoked.")

    perm.revoked_at = datetime.utcnow()
    perm.revoked_by = current_user.id
    await db.commit()
    return {"message": "Grant revoked.", "revoked_at": perm.revoked_at}


@router.get('/expiring')
async def get_expiring_grants(
    within_hours: int = 24,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin)
):
    """Returns all grants expiring within the next N hours."""
    cutoff = datetime.utcnow() + timedelta(hours=within_hours)
    now = datetime.utcnow()

    user_grants_res = await db.execute(
        select(ConnectorPermission).where(
            ConnectorPermission.expires_at.isnot(None),
            ConnectorPermission.expires_at > now,
            ConnectorPermission.expires_at <= cutoff,
            ConnectorPermission.revoked_at.is_(None),
        )
    )
    dept_grants_res = await db.execute(
        select(ConnectorPermissionDepartment).where(
            ConnectorPermissionDepartment.expires_at.isnot(None),
            ConnectorPermissionDepartment.expires_at > now,
            ConnectorPermissionDepartment.expires_at <= cutoff,
            ConnectorPermissionDepartment.revoked_at.is_(None),
        )
    )
    role_grants_res = await db.execute(
        select(ConnectorPermissionRole).where(
            ConnectorPermissionRole.expires_at.isnot(None),
            ConnectorPermissionRole.expires_at > now,
            ConnectorPermissionRole.expires_at <= cutoff,
            ConnectorPermissionRole.revoked_at.is_(None),
        )
    )

    user_grants = user_grants_res.scalars().all()
    dept_grants = dept_grants_res.scalars().all()
    role_grants = role_grants_res.scalars().all()

    def serialize_grant(g):
        is_active = is_grant_active(g)
        res = {
            "id": str(g.id),
            "valid_from": g.valid_from.isoformat() if g.valid_from else None,
            "expires_at": g.expires_at.isoformat() if g.expires_at else None,
            "revoked_at": g.revoked_at.isoformat() if g.revoked_at else None,
            "grant_reason": g.grant_reason,
            "is_active": is_active,
        }
        if hasattr(g, 'user_id'):
            res["user_id"] = str(g.user_id) if g.user_id else None
        if hasattr(g, 'connector_id'):
            res["connector_id"] = str(g.connector_id)
        if hasattr(g, 'department_id'):
            res["department_id"] = str(g.department_id)
        if hasattr(g, 'role_id'):
            res["role_id"] = str(g.role_id)
        if hasattr(g, 'connector_permission_id'):
            res["connector_permission_id"] = str(g.connector_permission_id)
        return res

    return {
        "within_hours": within_hours,
        "user_grants": [serialize_grant(g) for g in user_grants],
        "dept_grants": [serialize_grant(g) for g in dept_grants],
        "role_grants": [serialize_grant(g) for g in role_grants],
    }
