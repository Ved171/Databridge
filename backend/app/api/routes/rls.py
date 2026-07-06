import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_superadmin
from app.models import User, TableRLSFilter
from app.schemas import RLSFilterCreate, RLSFilterOut, RLSContextOut
from app.core.rls import resolve_rls_context, substitute_placeholders

logger = logging.getLogger("rls_routes")
router = APIRouter()


class RLSFilterUpdate(BaseModel):
    connector_id:       Optional[str] = None
    table_name:         Optional[str] = None
    filter_expression:  Optional[str] = None
    applies_to_role_id: Optional[str] = None
    applies_to_dept_id: Optional[str] = None
    applies_to_user_id: Optional[str] = None
    is_active:          Optional[bool] = None


async def get_current_superadmin_or_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    if current_user.is_superadmin:
        return current_user
    role = getattr(current_user, "role", None) or "member"
    if role not in ("superadmin", "admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Superadmin or admin access required")
    return current_user


@router.get("/filters/", response_model=List[RLSFilterOut])
async def list_rls_filters(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin_or_admin)
):
    res = await db.execute(select(TableRLSFilter))
    db_filters = list(res.scalars().all())

    # Fetch package RLS filters!
    from app.models import PackageRLSFilter, PackageDepartmentAssignment, PackageRoleAssignment, AccessPackage
    from app.core.deps import is_grant_active
    
    pkg_rls_res = await db.execute(
        select(PackageRLSFilter, AccessPackage)
        .join(AccessPackage, AccessPackage.id == PackageRLSFilter.package_id)
    )
    pkg_rls_rules = pkg_rls_res.all()
    
    virtual_rls = []
    for rule, pkg in pkg_rls_rules:
        # Fetch department and role assignments
        dept_assign_res = await db.execute(
            select(PackageDepartmentAssignment).where(PackageDepartmentAssignment.package_id == pkg.id)
        )
        dept_assigns = dept_assign_res.scalars().all()
        
        role_assign_res = await db.execute(
            select(PackageRoleAssignment).where(PackageRoleAssignment.package_id == pkg.id)
        )
        role_assigns = role_assign_res.scalars().all()
        
        for da in dept_assigns:
            if is_grant_active(da):
                virtual_rls.append({
                    "id": str(rule.id),
                    "connector_id": str(rule.connector_id),
                    "table_name": rule.table_name,
                    "filter_expression": f"{rule.filter_expression} /* Package: {pkg.name} */",
                    "applies_to_role_id": str(da.role_id) if da.role_id else None,
                    "applies_to_dept_id": str(da.department_id),
                    "applies_to_user_id": None,
                    "is_active": pkg.is_active,
                    "created_at": pkg.created_at,
                    "is_package_rule": True,
                })
                
        for ra in role_assigns:
            if is_grant_active(ra):
                virtual_rls.append({
                    "id": str(rule.id),
                    "connector_id": str(rule.connector_id),
                    "table_name": rule.table_name,
                    "filter_expression": f"{rule.filter_expression} /* Package: {pkg.name} */",
                    "applies_to_role_id": str(ra.role_id),
                    "applies_to_dept_id": None,
                    "applies_to_user_id": None,
                    "is_active": pkg.is_active,
                    "created_at": pkg.created_at,
                    "is_package_rule": True,
                })
                
    return db_filters + virtual_rls


@router.post("/filters/", response_model=RLSFilterOut)
async def create_rls_filter(
    payload: RLSFilterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin_or_admin)
):
    new_filter = TableRLSFilter(
        id=uuid.uuid4(),
        connector_id=payload.connector_id,
        table_name=payload.table_name,
        filter_expression=payload.filter_expression,
        applies_to_role_id=uuid.UUID(payload.applies_to_role_id) if payload.applies_to_role_id else None,
        applies_to_dept_id=uuid.UUID(payload.applies_to_dept_id) if payload.applies_to_dept_id else None,
        applies_to_user_id=uuid.UUID(payload.applies_to_user_id) if payload.applies_to_user_id else None,
        created_by=uuid.UUID(str(current_user.id)),
        is_active=True
    )
    db.add(new_filter)
    await db.commit()
    await db.refresh(new_filter)
    return new_filter


@router.patch("/filters/{id}", response_model=RLSFilterOut)
async def update_rls_filter(
    id: str,
    payload: RLSFilterUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin_or_admin)
):
    rls_filter = await db.get(TableRLSFilter, uuid.UUID(id))
    if not rls_filter:
        raise HTTPException(status_code=404, detail="RLS filter not found.")

    update_data = payload.model_dump(exclude_unset=True)
    
    # Handle UUID conversions safely
    for field in ("applies_to_role_id", "applies_to_dept_id", "applies_to_user_id"):
        if field in update_data:
            val = update_data[field]
            update_data[field] = uuid.UUID(val) if val else None

    for key, value in update_data.items():
        setattr(rls_filter, key, value)

    # Perform target validation on the updated model state
    if not any([rls_filter.applies_to_role_id, rls_filter.applies_to_dept_id, rls_filter.applies_to_user_id]):
        raise HTTPException(
            status_code=400,
            detail="At least one of applies_to_role_id, applies_to_dept_id, applies_to_user_id must be set."
        )

    # Validate filter expression if updated
    if payload.filter_expression is not None:
        import re
        if not re.search(r'\{[\w.]+\}', rls_filter.filter_expression):
            raise HTTPException(
                status_code=400,
                detail="filter_expression must contain at least one {placeholder}."
            )

    await db.commit()
    await db.refresh(rls_filter)
    return rls_filter


class BulkDeleteFiltersPayload(BaseModel):
    ids: List[str]


@router.post("/filters/bulk-delete")
async def bulk_delete_rls_filters(
    payload: BulkDeleteFiltersPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin_or_admin)
):
    import uuid
    for filter_id in payload.ids:
        rls_filter = await db.get(TableRLSFilter, uuid.UUID(filter_id))
        if rls_filter:
            await db.delete(rls_filter)
    await db.commit()
    return {"status": "success", "message": f"Successfully deleted {len(payload.ids)} RLS filters."}


@router.delete("/filters/{id}")
async def delete_rls_filter(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin_or_admin)
):
    rls_filter = await db.get(TableRLSFilter, uuid.UUID(id))
    if not rls_filter:
        raise HTTPException(status_code=404, detail="RLS filter not found.")

    await db.delete(rls_filter)
    await db.commit()
    return {"status": "success", "message": "RLS filter deleted successfully."}


@router.get("/context/{user_id}", response_model=RLSContextOut)
async def get_rls_context(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin)
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    context = await resolve_rls_context(user, db)
    
    managed_user_ids = context["manager.managed_user_ids"].split(",") if context["manager.managed_user_ids"] else []
    managed_codes = context["manager.managed_codes"].split(",") if context["manager.managed_codes"] else []
    
    return RLSContextOut(
        user_id=context["user.id"],
        user_email=context["user.email"],
        user_employee_code=context["user.employee_code"] or None,
        managed_user_ids=managed_user_ids,
        managed_codes=managed_codes,
        managed_count=int(context["manager.managed_count"]),
        is_manager=context["manager.is_manager"] == "true"
    )


@router.get("/preview")
async def preview_rls_filter(
    user_id: str,
    filter_expression: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin)
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    context = await resolve_rls_context(user, db)
    try:
        substituted, _ = substitute_placeholders(filter_expression, context)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "input":       filter_expression,
        "substituted": substituted,
        "context":     context,
    }


#  GAP 4: Global RLS settings (kill switch) 

@router.get("/settings/")
async def get_rls_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin)
):
    from app.models import RLSGlobalSetting
    result = await db.execute(
        select(RLSGlobalSetting.value).where(RLSGlobalSetting.key == "rls_enabled")
    )
    val = result.scalar_one_or_none()
    return {"rls_enabled": val != "false" if val is not None else True}


@router.put("/settings/")
async def update_rls_settings(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin)
):
    from app.models import RLSGlobalSetting
    rls_enabled = payload.get("rls_enabled")
    if rls_enabled is None:
        raise HTTPException(status_code=400, detail="rls_enabled is required")

    result = await db.execute(
        select(RLSGlobalSetting).where(RLSGlobalSetting.key == "rls_enabled")
    )
    setting = result.scalar_one_or_none()

    str_val = "true" if rls_enabled else "false"
    if setting:
        setting.value = str_val
        setting.updated_by = uuid.UUID(str(current_user.id))
    else:
        setting = RLSGlobalSetting(
            id=uuid.uuid4(),
            key="rls_enabled",
            value=str_val,
            updated_by=uuid.UUID(str(current_user.id)),
        )
        db.add(setting)

    await db.commit()

    # Invalidate the module-level cache so the change takes effect immediately
    from app.core.query_runner import _rls_enabled_cache
    _rls_enabled_cache["fetched_at"] = 0.0

    return {"rls_enabled": rls_enabled}


#  GAP 2: Apply standard manager hierarchy filters 

class StandardHierarchyPayload(BaseModel):
    connector_id: str
    table_name: str
    identity_column: str
    scope_level: int


@router.post("/apply-standard-hierarchy/")
async def apply_standard_hierarchy(
    payload: StandardHierarchyPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin_or_admin)
):
    import asyncio
    from app.models import Role, User
    from app.core.database import AsyncSessionLocal

    # 400 check identity_column
    if not payload.identity_column or " " in payload.identity_column:
        raise HTTPException(
            status_code=400,
            detail="Identity column cannot be empty or contain spaces."
        )

    # 409 Check for existing active filters on this connector+table
    existing = await db.execute(
        select(TableRLSFilter).where(
            TableRLSFilter.connector_id == payload.connector_id,
            TableRLSFilter.table_name == payload.table_name,
            TableRLSFilter.is_active == True,
        )
    )
    if existing.scalars().first() is not None:
        raise HTTPException(
            status_code=409,
            detail="Active RLS filters already exist for this table on this connector. Delete them first or use the manual filter editor."
        )

    # Find roles assigned to any superadmin user (is_superadmin=True) to identify levels that cover superadmins
    superadmin_levels_query = await db.execute(
        select(Role.level)
        .join(User, User.role_id == Role.id)
        .where(User.is_superadmin == True, Role.deleted_at.is_(None))
    )
    super_levels = superadmin_levels_query.scalars().all()
    min_super_level = min(super_levels) if super_levels else None

    # Query active roles >= scope_level, excluding superadmin levels
    query = select(Role).where(
        Role.level >= payload.scope_level,
        Role.deleted_at.is_(None)
    )
    if min_super_level is not None:
        query = query.where(Role.level < min_super_level)
    
    query = query.order_by(Role.level.asc())
    roles_res = await db.execute(query)
    roles = roles_res.scalars().all()

    if not roles:
        raise HTTPException(
            status_code=400,
            detail="No roles found at or above the specified scope level."
        )

    col = payload.identity_column
    tasks = []
    for role in roles:
        if role.level == payload.scope_level:
            expr = f"{col} = '{{user.employee_code}}'"
        else:
            expr = f"{col} IN ({{manager.managed_codes_quoted}}) OR {col} = '{{user.employee_code}}'"

        f_data = {
            "id": uuid.uuid4(),
            "connector_id": payload.connector_id,
            "table_name": payload.table_name,
            "filter_expression": expr,
            "applies_to_role_id": role.id,
            "created_by": uuid.UUID(str(current_user.id)),
            "is_active": True,
        }

        async def create_and_commit(data):
            async with AsyncSessionLocal() as local_db:
                new_filter = TableRLSFilter(
                    id=data["id"],
                    connector_id=data["connector_id"],
                    table_name=data["table_name"],
                    filter_expression=data["filter_expression"],
                    applies_to_role_id=data["applies_to_role_id"],
                    created_by=data["created_by"],
                    is_active=data["is_active"]
                )
                local_db.add(new_filter)
                await local_db.commit()
                await local_db.refresh(new_filter)
                return new_filter

        tasks.append(create_and_commit(f_data))

    created_filters = await asyncio.gather(*tasks)

    return {
        "created": len(created_filters),
        "filters": [RLSFilterOut.model_validate(f) for f in created_filters]
    }

