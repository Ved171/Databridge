import uuid
import logging
import re
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_superadmin, is_grant_active, resolve_department_chain
from app.models import (
    User, AccessPackage, PackageConnectorRule, PackageTableRule,
    PackageRLSFilter, PackageDepartmentAssignment, PackageRoleAssignment
)
from app.schemas import (
    PackageCreate, PackageOut, PackageAssignIn,
    PackageConnectorRuleIn, PackageTableRuleIn, PackageRLSFilterIn
)

logger = logging.getLogger("packages_routes")
router = APIRouter()


def to_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        import datetime as dt_module
        return dt.astimezone(dt_module.timezone.utc).replace(tzinfo=None)
    return dt


class PackageUpdate(BaseModel):
    name:              Optional[str] = None
    description:       Optional[str] = None
    color:             Optional[str] = None
    is_active:         Optional[bool] = None
    connector_rules:   Optional[List[PackageConnectorRuleIn]] = None
    table_rules:       Optional[List[PackageTableRuleIn]] = None
    rls_filters:       Optional[List[PackageRLSFilterIn]] = None


async def get_current_superadmin_or_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    if current_user.is_superadmin:
        return current_user
    role = getattr(current_user, "role", None) or "member"
    if role not in ("superadmin", "admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Superadmin or admin access required")
    return current_user


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_-]+', '-', s)
    return s


async def get_package_with_relations(package_id: uuid.UUID, db: AsyncSession) -> Optional[AccessPackage]:
    from sqlalchemy.orm import selectinload
    stmt = (
        select(AccessPackage)
        .options(
            selectinload(AccessPackage.connector_rules),
            selectinload(AccessPackage.table_rules),
            selectinload(AccessPackage.rls_filters),
            selectinload(AccessPackage.dept_assignments),
            selectinload(AccessPackage.role_assignments)
        )
        .where(AccessPackage.id == package_id)
    )
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


@router.get("/", response_model=List[PackageOut])
async def list_packages(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin_or_admin)
):
    from sqlalchemy.orm import selectinload
    stmt = (
        select(AccessPackage)
        .options(
            selectinload(AccessPackage.connector_rules),
            selectinload(AccessPackage.table_rules),
            selectinload(AccessPackage.rls_filters),
            selectinload(AccessPackage.dept_assignments),
            selectinload(AccessPackage.role_assignments)
        )
    )
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/", response_model=PackageOut)
async def create_package(
    payload: PackageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin)
):
    slug = slugify(payload.name)
    
    # Check uniqueness
    res = await db.execute(select(AccessPackage).where((AccessPackage.name == payload.name) | (AccessPackage.slug == slug)))
    if res.scalars().first():
        raise HTTPException(status_code=400, detail="Package with this name or slug already exists.")

    new_package = AccessPackage(
        id=uuid.uuid4(),
        name=payload.name,
        slug=slug,
        description=payload.description,
        color=payload.color,
        is_active=True,
        created_by=uuid.UUID(str(current_user.id))
    )
    db.add(new_package)
    await db.flush()

    for r in payload.connector_rules:
        rule = PackageConnectorRule(
            id=uuid.uuid4(),
            package_id=new_package.id,
            connector_id=r.connector_id,
            is_deny=r.is_deny,
            can_read=r.can_read,
            can_create=r.can_create,
            can_update=r.can_update,
            can_delete=r.can_delete
        )
        db.add(rule)

    for t in payload.table_rules:
        rule = PackageTableRule(
            id=uuid.uuid4(),
            package_id=new_package.id,
            connector_id=t.connector_id,
            table_name=t.table_name,
            is_deny=t.is_deny,
            can_read=t.can_read,
            can_create=t.can_create,
            can_update=t.can_update,
            can_delete=t.can_delete
        )
        db.add(rule)

    for f in payload.rls_filters:
        rule = PackageRLSFilter(
            id=uuid.uuid4(),
            package_id=new_package.id,
            connector_id=f.connector_id,
            table_name=f.table_name,
            filter_expression=f.filter_expression
        )
        db.add(rule)

    await db.commit()
    return await get_package_with_relations(new_package.id, db)


@router.get("/{id}", response_model=PackageOut)
async def get_package(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin_or_admin)
):
    pkg_uuid = uuid.UUID(id)
    pkg = await get_package_with_relations(pkg_uuid, db)
    if not pkg:
        raise HTTPException(status_code=404, detail="Access package not found.")
    return pkg


@router.patch("/{id}", response_model=PackageOut)
async def update_package(
    id: str,
    payload: PackageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin)
):
    pkg_uuid = uuid.UUID(id)
    pkg = await get_package_with_relations(pkg_uuid, db)
    if not pkg:
        raise HTTPException(status_code=404, detail="Access package not found.")

    if payload.name is not None:
        if payload.name != pkg.name:
            res = await db.execute(select(AccessPackage).where(AccessPackage.name == payload.name))
            if res.scalars().first():
                raise HTTPException(status_code=400, detail="Package with this name already exists.")
            pkg.name = payload.name

    if payload.description is not None:
        pkg.description = payload.description
    if payload.color is not None:
        pkg.color = payload.color
    if payload.is_active is not None:
        pkg.is_active = payload.is_active

    # Replace rules if provided in payload
    if payload.connector_rules is not None:
        await db.execute(delete(PackageConnectorRule).where(PackageConnectorRule.package_id == pkg_uuid))
        for r in payload.connector_rules:
            rule = PackageConnectorRule(
                id=uuid.uuid4(),
                package_id=pkg_uuid,
                connector_id=r.connector_id,
                is_deny=r.is_deny,
                can_read=r.can_read,
                can_create=r.can_create,
                can_update=r.can_update,
                can_delete=r.can_delete
            )
            db.add(rule)

    if payload.table_rules is not None:
        await db.execute(delete(PackageTableRule).where(PackageTableRule.package_id == pkg_uuid))
        for t in payload.table_rules:
            rule = PackageTableRule(
                id=uuid.uuid4(),
                package_id=pkg_uuid,
                connector_id=t.connector_id,
                table_name=t.table_name,
                is_deny=t.is_deny,
                can_read=t.can_read,
                can_create=t.can_create,
                can_update=t.can_update,
                can_delete=t.can_delete
            )
            db.add(rule)

    if payload.rls_filters is not None:
        await db.execute(delete(PackageRLSFilter).where(PackageRLSFilter.package_id == pkg_uuid))
        for f in payload.rls_filters:
            rule = PackageRLSFilter(
                id=uuid.uuid4(),
                package_id=pkg_uuid,
                connector_id=f.connector_id,
                table_name=f.table_name,
                filter_expression=f.filter_expression
            )
            db.add(rule)

    await db.commit()
    return await get_package_with_relations(pkg_uuid, db)


@router.delete("/{id}")
async def delete_package(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin)
):
    pkg_uuid = uuid.UUID(id)
    pkg = await get_package_with_relations(pkg_uuid, db)
    if not pkg:
        raise HTTPException(status_code=404, detail="Access package not found.")

    # Check active assignments using unified helper
    active_depts = [a for a in pkg.dept_assignments if is_grant_active(a)]
    active_roles = [a for a in pkg.role_assignments if is_grant_active(a)]
    
    total_active = len(active_depts) + len(active_roles)
    if total_active > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete package. Active assignments exist: {total_active} assignments found."
        )

    await db.delete(pkg)
    await db.commit()
    return {"status": "success", "message": "Package deleted successfully.", "active_assignments_count": total_active}


@router.post("/{id}/assign", response_model=PackageOut)
async def assign_package(
    id: str,
    payload: PackageAssignIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin)
):
    pkg_uuid = uuid.UUID(id)
    pkg = await get_package_with_relations(pkg_uuid, db)
    if not pkg:
        raise HTTPException(status_code=404, detail="Access package not found.")

    # Department assignments (unscoped — all roles in dept)
    for dept_id_str in payload.department_ids:
        dept_uuid = uuid.UUID(dept_id_str)
        stmt = select(PackageDepartmentAssignment).where(
            PackageDepartmentAssignment.package_id == pkg_uuid,
            PackageDepartmentAssignment.department_id == dept_uuid,
            PackageDepartmentAssignment.role_id.is_(None)
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        
        if existing:
            existing.valid_from = to_naive_utc(payload.valid_from)
            existing.expires_at = to_naive_utc(payload.expires_at)
            existing.revoked_at = None
            existing.revoked_by = None
            existing.assigned_by = uuid.UUID(str(current_user.id))
            existing.assigned_at = datetime.utcnow()
        else:
            new_assign = PackageDepartmentAssignment(
                id=uuid.uuid4(),
                package_id=pkg_uuid,
                department_id=dept_uuid,
                role_id=None,
                valid_from=to_naive_utc(payload.valid_from),
                expires_at=to_naive_utc(payload.expires_at),
                assigned_by=uuid.UUID(str(current_user.id)),
                assigned_at=datetime.utcnow()
            )
            db.add(new_assign)

    # Role assignments (standalone)
    for role_id_str in payload.role_ids:
        role_uuid = uuid.UUID(role_id_str)
        stmt = select(PackageRoleAssignment).where(
            PackageRoleAssignment.package_id == pkg_uuid,
            PackageRoleAssignment.role_id == role_uuid
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        
        if existing:
            existing.valid_from = to_naive_utc(payload.valid_from)
            existing.expires_at = to_naive_utc(payload.expires_at)
            existing.revoked_at = None
            existing.revoked_by = None
            existing.assigned_by = uuid.UUID(str(current_user.id))
            existing.assigned_at = datetime.utcnow()
        else:
            new_assign = PackageRoleAssignment(
                id=uuid.uuid4(),
                package_id=pkg_uuid,
                role_id=role_uuid,
                valid_from=to_naive_utc(payload.valid_from),
                expires_at=to_naive_utc(payload.expires_at),
                assigned_by=uuid.UUID(str(current_user.id)),
                assigned_at=datetime.utcnow()
            )
            db.add(new_assign)

    # Dept + Role combination assignments (scoped)
    for combo in payload.dept_role_assignments:
        dept_uuid = uuid.UUID(combo.department_id)
        role_uuid = uuid.UUID(combo.role_id)
        stmt = select(PackageDepartmentAssignment).where(
            PackageDepartmentAssignment.package_id == pkg_uuid,
            PackageDepartmentAssignment.department_id == dept_uuid,
            PackageDepartmentAssignment.role_id == role_uuid
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            existing.valid_from = to_naive_utc(payload.valid_from)
            existing.expires_at = to_naive_utc(payload.expires_at)
            existing.revoked_at = None
            existing.revoked_by = None
            existing.assigned_by = uuid.UUID(str(current_user.id))
            existing.assigned_at = datetime.utcnow()
        else:
            new_assign = PackageDepartmentAssignment(
                id=uuid.uuid4(),
                package_id=pkg_uuid,
                department_id=dept_uuid,
                role_id=role_uuid,
                valid_from=to_naive_utc(payload.valid_from),
                expires_at=to_naive_utc(payload.expires_at),
                assigned_by=uuid.UUID(str(current_user.id)),
                assigned_at=datetime.utcnow()
            )
            db.add(new_assign)

    await db.commit()
    return await get_package_with_relations(pkg_uuid, db)


@router.post("/{id}/revoke/dept/{dept_id}")
async def revoke_dept_assignment(
    id: str,
    dept_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin)
):
    pkg_uuid = uuid.UUID(id)
    dept_uuid = uuid.UUID(dept_id)
    
    stmt = select(PackageDepartmentAssignment).where(
        PackageDepartmentAssignment.package_id == pkg_uuid,
        PackageDepartmentAssignment.department_id == dept_uuid,
        PackageDepartmentAssignment.role_id.is_(None),
        PackageDepartmentAssignment.revoked_at.is_(None)
    )
    res = await db.execute(stmt)
    assign = res.scalar_one_or_none()
    if not assign:
        raise HTTPException(status_code=404, detail="Active department assignment not found.")
        
    assign.revoked_at = datetime.utcnow()
    assign.revoked_by = uuid.UUID(str(current_user.id))
    await db.commit()
    return {"status": "success", "message": "Department package assignment revoked."}


@router.post("/{id}/revoke/role/{role_id}")
async def revoke_role_assignment(
    id: str,
    role_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin)
):
    pkg_uuid = uuid.UUID(id)
    role_uuid = uuid.UUID(role_id)
    
    stmt = select(PackageRoleAssignment).where(
        PackageRoleAssignment.package_id == pkg_uuid,
        PackageRoleAssignment.role_id == role_uuid,
        PackageRoleAssignment.revoked_at.is_(None)
    )
    res = await db.execute(stmt)
    assign = res.scalar_one_or_none()
    if not assign:
        raise HTTPException(status_code=404, detail="Active role assignment not found.")
        
    assign.revoked_at = datetime.utcnow()
    assign.revoked_by = uuid.UUID(str(current_user.id))
    await db.commit()
    return {"status": "success", "message": "Role package assignment revoked."}


@router.post("/{id}/revoke/assignment/{assignment_id}")
async def revoke_assignment_by_id(
    id: str,
    assignment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin)
):
    """Revoke any dept or role assignment by its unique assignment row ID."""
    pkg_uuid = uuid.UUID(id)
    assign_uuid = uuid.UUID(assignment_id)

    # Try dept assignment first
    stmt = select(PackageDepartmentAssignment).where(
        PackageDepartmentAssignment.id == assign_uuid,
        PackageDepartmentAssignment.package_id == pkg_uuid,
        PackageDepartmentAssignment.revoked_at.is_(None)
    )
    res = await db.execute(stmt)
    assign = res.scalar_one_or_none()
    if assign:
        assign.revoked_at = datetime.utcnow()
        assign.revoked_by = uuid.UUID(str(current_user.id))
        await db.commit()
        return {"status": "success", "message": "Department assignment revoked."}

    # Try role assignment
    stmt = select(PackageRoleAssignment).where(
        PackageRoleAssignment.id == assign_uuid,
        PackageRoleAssignment.package_id == pkg_uuid,
        PackageRoleAssignment.revoked_at.is_(None)
    )
    res = await db.execute(stmt)
    assign = res.scalar_one_or_none()
    if assign:
        assign.revoked_at = datetime.utcnow()
        assign.revoked_by = uuid.UUID(str(current_user.id))
        await db.commit()
        return {"status": "success", "message": "Role assignment revoked."}

    raise HTTPException(status_code=404, detail="Active assignment not found.")


@router.get("/user/{user_id}/active")
async def get_user_active_packages(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin)
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    role_chain = [str(user.role_id)] if user.role_id else []
    dept_chain = await resolve_department_chain(user.department_id, db)

    dept_assignments = await db.execute(
        select(PackageDepartmentAssignment)
        .where(
            PackageDepartmentAssignment.department_id.in_(dept_chain),
            PackageDepartmentAssignment.revoked_at.is_(None),
        )
    )
    role_assignments = await db.execute(
        select(PackageRoleAssignment)
        .where(
            PackageRoleAssignment.role_id.in_(role_chain),
            PackageRoleAssignment.revoked_at.is_(None),
        )
    )

    active_packages = []
    
    # Resolve names of departments and roles for display
    from app.models import Department, Role

    # Collect all role IDs we might need names for
    all_role_ids = set(role_chain)
    dept_rows_list = list(dept_assignments.scalars())
    for row in dept_rows_list:
        if row.role_id:
            all_role_ids.add(str(row.role_id))

    res_depts = await db.execute(select(Department).where(Department.id.in_(dept_chain)))
    dept_names = {str(d.id): d.name for d in res_depts.scalars().all()}
    
    if all_role_ids:
        res_roles = await db.execute(select(Role).where(Role.id.in_(list(all_role_ids))))
        role_names = {str(r.id): r.name for r in res_roles.scalars().all()}
    else:
        role_names = {}

    for row in dept_rows_list:
        if not is_grant_active(row):
            continue
        # If this assignment has a role_id, check the user matches
        if row.role_id is not None:
            if str(row.role_id) not in role_chain:
                continue  # user doesn't match scoped role

        pkg = await get_package_with_relations(row.package_id, db)
        if pkg and pkg.is_active:
            dept_name = dept_names.get(str(row.department_id), "Unknown Department")
            if row.role_id is not None:
                scoped_role_name = role_names.get(str(row.role_id), "Unknown Role")
                source_detail = f"Department: {dept_name} + Role: {scoped_role_name}"
            else:
                source_detail = f"Department: {dept_name}"
            active_packages.append({
                "package": {
                    "id": str(pkg.id),
                    "name": pkg.name,
                    "description": pkg.description,
                    "color": pkg.color,
                    "is_active": pkg.is_active
                },
                "source_type": "department",
                "source_name": dept_name,
                "source_detail": source_detail
            })

    for row in role_assignments.scalars():
        if is_grant_active(row):
            pkg = await get_package_with_relations(row.package_id, db)
            if pkg and pkg.is_active:
                role_name = role_names.get(str(row.role_id), "Unknown Role")
                active_packages.append({
                    "package": {
                        "id": str(pkg.id),
                        "name": pkg.name,
                        "description": pkg.description,
                        "color": pkg.color,
                        "is_active": pkg.is_active
                    },
                    "source_type": "role",
                    "source_name": role_name,
                    "source_detail": f"Role: {role_name}"
                })

    return active_packages


