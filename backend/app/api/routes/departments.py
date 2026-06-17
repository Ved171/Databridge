from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from typing import List

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_superadmin
from app.models import User, Department, Role
from app.schemas import DepartmentCreate, DepartmentUpdate, DepartmentOut

router = APIRouter()


@router.get("/roles")
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all available roles for the default role dropdown.
    """
    result = await db.execute(select(Role).order_by(Role.name))
    return [{"id": str(r.id), "name": r.name} for r in result.scalars().all()]


@router.get("/", response_model=List[DepartmentOut])
async def list_departments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all active/inactive departments. Accessible by all authenticated users for dropdowns.
    Computes the member count dynamically for each department.
    """
    stmt = (
        select(Department, func.count(User.id).label("member_count"))
        .outerjoin(User, User.department_id == Department.id)
        .group_by(Department.id)
        .order_by(Department.name)
    )
    result = await db.execute(stmt)
    departments_with_count = []
    
    for row in result.all():
        dept, member_count = row
        departments_with_count.append({
            "id": str(dept.id),
            "name": dept.name,
            "slug": dept.slug,
            "color": dept.color,
            "is_active": dept.is_active,
            "is_system": dept.is_system,
            "default_role_id": str(dept.default_role_id) if dept.default_role_id else None,
            "parent_department_id": str(dept.parent_department_id) if dept.parent_department_id else None,
            "member_count": member_count
        })
        
    return departments_with_count


@router.post("/", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    """
    Create a new department. Superadmin only.
    Slug is generated from name (lowercase, spaces to hyphens) and is immutable after creation.
    """
    # Clean and check name uniqueness
    cleaned_name = payload.name.strip()
    if not cleaned_name:
        raise HTTPException(status_code=400, detail="Department name cannot be empty.")

    # Check uniqueness
    existing = await db.execute(select(Department).where(func.lower(Department.name) == cleaned_name.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Department with name '{cleaned_name}' already exists.")

    # Auto-generate slug from name (lowercase, spaces -> hyphens)
    slug = cleaned_name.lower().replace(" ", "-")
    # Clean duplicate hyphens
    while "--" in slug:
        slug = slug.replace("--", "-")
    slug = slug.strip("-")

    # Check slug uniqueness
    existing_slug = await db.execute(select(Department).where(Department.slug == slug))
    if existing_slug.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Generated slug '{slug}' already exists.")

    new_dept = Department(
        name=cleaned_name,
        slug=slug,
        color=payload.color,
        default_role_id=payload.default_role_id,
        parent_department_id=payload.parent_department_id,
        is_active=True,
        is_system=False,
    )
    db.add(new_dept)
    await db.flush()
    await db.refresh(new_dept)

    return {
        "id": str(new_dept.id),
        "name": new_dept.name,
        "slug": new_dept.slug,
        "color": new_dept.color,
        "is_active": new_dept.is_active,
        "is_system": new_dept.is_system,
        "default_role_id": str(new_dept.default_role_id) if new_dept.default_role_id else None,
        "parent_department_id": str(new_dept.parent_department_id) if new_dept.parent_department_id else None,
        "member_count": 0
    }


@router.patch("/{id}", response_model=DepartmentOut)
async def update_department(
    id: str,
    payload: DepartmentUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    """
    Update a department. Superadmin only.
    Validates that 'slug' is not present in the raw request payload.
    """
    # Check if slug is in the raw JSON payload
    try:
        body = await request.json()
        if body and "slug" in body:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department slug is immutable after creation."
            )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        # If request body is empty or not JSON, we continue

    # Retrieve department
    result = await db.execute(select(Department).where(Department.id == id))
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    # If updating name, check uniqueness
    if payload.name is not None:
        cleaned_name = payload.name.strip()
        if not cleaned_name:
            raise HTTPException(status_code=400, detail="Department name cannot be empty.")
        
        if cleaned_name.lower() != dept.name.lower():
            existing = await db.execute(
                select(Department)
                .where(func.lower(Department.name) == cleaned_name.lower())
                .where(Department.id != id)
            )
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=400, detail=f"Department with name '{cleaned_name}' already exists.")
            dept.name = cleaned_name

    # Apply other fields
    if payload.color is not None:
        dept.color = payload.color
    if payload.is_active is not None:
        dept.is_active = payload.is_active
    if payload.default_role_id is not None:
        dept.default_role_id = payload.default_role_id
        
    await db.flush()
    await db.refresh(dept)

    # Get member count
    members_res = await db.execute(select(func.count(User.id)).where(User.department_id == dept.id))
    member_count = members_res.scalar_one()

    return {
        "id": str(dept.id),
        "name": dept.name,
        "slug": dept.slug,
        "color": dept.color,
        "is_active": dept.is_active,
        "is_system": dept.is_system,
        "default_role_id": str(dept.default_role_id) if dept.default_role_id else None,
        "parent_department_id": str(dept.parent_department_id) if dept.parent_department_id else None,
        "member_count": member_count
    }


@router.delete("/{id}")
async def delete_department(
    id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    """
    Delete a department. Superadmin only.
    Blocks deletion if department has is_system=True or if any users are assigned.
    """
    # Retrieve department
    result = await db.execute(select(Department).where(Department.id == id))
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    # Block if is_system=True
    if getattr(dept, "is_system", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System departments cannot be deleted."
        )

    # Block if users are assigned
    count_res = await db.execute(select(func.count(User.id)).where(User.department_id == id))
    user_count = count_res.scalar_one()
    
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Cannot delete department with assigned users.",
                "assigned_users": user_count
            }
        )

    await db.delete(dept)
    await db.flush()

    return {"status": "success", "message": "Department deleted successfully."}
