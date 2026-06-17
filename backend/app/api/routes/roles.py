from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.core.deps import (
    get_current_user,
    get_current_superadmin,
    get_current_admin_or_wsadmin,
    would_create_cycle,
    resolve_role_chain
)
from app.models import User, Role, UserManagerAssignment
from app.schemas import RoleCreate, RoleUpdate, RoleOut, RoleTreeNode, UserOut

router = APIRouter()


@router.get("/", response_model=List[RoleOut])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all active roles. Accessible by all authenticated users for dropdowns.
    Computes user member counts dynamically.
    """
    stmt = (
        select(Role, func.count(User.id).label("member_count"))
        .outerjoin(User, User.role_id == Role.id)
        .where(Role.deleted_at.is_(None))
        .group_by(Role.id)
        .order_by(Role.level)
    )
    result = await db.execute(stmt)
    roles_with_count = []
    
    for row in result.all():
        role, member_count = row
        roles_with_count.append({
            "id": str(role.id),
            "name": role.name,
            "slug": role.slug,
            "level": role.level,
            "color": role.color,
            "is_system": role.is_system,
            "is_active": role.is_active,
            "parent_role_id": str(role.parent_role_id) if role.parent_role_id else None,
            "member_count": member_count
        })
        
    return roles_with_count


@router.get("/tree", response_model=List[RoleTreeNode])
async def get_roles_tree(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get nested role hierarchy tree. Accessible by all authenticated users.
    """
    stmt = (
        select(Role, func.count(User.id).label("member_count"))
        .outerjoin(User, User.role_id == Role.id)
        .where(Role.deleted_at.is_(None))
        .group_by(Role.id)
        .order_by(Role.level)
    )
    result = await db.execute(stmt)
    
    nodes = {}
    for row in result.all():
        role, member_count = row
        nodes[str(role.id)] = {
            "id": str(role.id),
            "name": role.name,
            "level": role.level,
            "member_count": member_count,
            "color": role.color,
            "is_system": role.is_system,
            "is_active": role.is_active,
            "parent_role_id": str(role.parent_role_id) if role.parent_role_id else None,
            "children": []
        }
        
    roots = []
    for r_id, node in nodes.items():
        parent_id = node["parent_role_id"]
        if parent_id and parent_id in nodes:
            nodes[parent_id]["children"].append(node)
        else:
            roots.append(node)
            
    def sort_tree(node_list):
        node_list.sort(key=lambda x: x["level"])
        for n in node_list:
            if n["children"]:
                sort_tree(n["children"])
                
    sort_tree(roots)
    return roots


@router.get("/{id}/chain", response_model=List[str])
async def get_role_chain(
    id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    """
    Get role path to roots. Superadmin only.
    """
    return await resolve_role_chain(id, db)


async def recalculate_role_levels(db: AsyncSession) -> None:
    """
    Recalculates levels for all active roles bottom-up.
    - Leaf roles (no children) get level 1.
    - Parent roles get max(child_levels) + 1.
    """
    stmt = select(Role).where(Role.deleted_at.is_(None))
    res = await db.execute(stmt)
    roles = res.scalars().all()

    role_dict = {str(role.id): role for role in roles}
    memo = {}

    def get_level(role_id_str):
        if role_id_str in memo:
            return memo[role_id_str]

        # Find immediate children of this role
        children = [r for r in roles if r.parent_role_id and str(r.parent_role_id) == role_id_str]
        if not children:
            memo[role_id_str] = 1
            return 1

        max_child_level = max(get_level(str(child.id)) for child in children)
        memo[role_id_str] = max_child_level + 1
        return memo[role_id_str]

    for role in roles:
        role.level = get_level(str(role.id))
        db.add(role)


@router.post("/", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    """
    Create a new role. Superadmin only.
    """
    cleaned_name = payload.name.strip()
    if not cleaned_name:
        raise HTTPException(status_code=400, detail="Role name cannot be empty.")

    # Unique check
    existing = await db.execute(select(Role).where(func.lower(Role.name) == cleaned_name.lower(), Role.deleted_at.is_(None)))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Role with name '{cleaned_name}' already exists.")

    slug = cleaned_name.lower().replace(" ", "-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    slug = slug.strip("-")

    # Check slug uniqueness
    existing_slug = await db.execute(select(Role).where(Role.slug == slug, Role.deleted_at.is_(None)))
    if existing_slug.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Generated slug '{slug}' already exists.")

    # Validate parent if provided
    import uuid
    parent_uuid = None
    if payload.parent_role_id:
        p_res = await db.execute(select(Role).where(Role.id == payload.parent_role_id, Role.deleted_at.is_(None)))
        if not p_res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Parent role not found.")
        parent_uuid = uuid.UUID(str(payload.parent_role_id))

    new_role = Role(
        name=cleaned_name,
        slug=slug,
        level=1,
        color=payload.color,
        parent_role_id=parent_uuid,
        is_system=False,
        is_active=True,
    )
    db.add(new_role)
    await db.flush()
    await recalculate_role_levels(db)
    await db.flush()
    await db.refresh(new_role)

    return {
        "id": str(new_role.id),
        "name": new_role.name,
        "slug": new_role.slug,
        "level": new_role.level,
        "color": new_role.color,
        "is_system": new_role.is_system,
        "is_active": new_role.is_active,
        "parent_role_id": str(new_role.parent_role_id) if new_role.parent_role_id else None,
        "member_count": 0
    }


@router.patch("/{id}", response_model=RoleOut)
async def update_role(
    id: str,
    payload: RoleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    """
    Update a role. Superadmin only.
    Enforces slug immutability, blocks system role updates, and prevents hierarchy cycles.
    """
    # Reject if slug is in payload
    try:
        body = await request.json()
        if body and "slug" in body:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role slug is immutable after creation."
            )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e

    # Retrieve role
    result = await db.execute(select(Role).where(Role.id == id, Role.deleted_at.is_(None)))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Block modification if system role
    if getattr(role, "is_system", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System roles cannot be modified."
        )

    # Validate parent and check cycles
    body = await request.json()
    if "parent_role_id" in body:
        new_parent_id = body["parent_role_id"]
        if new_parent_id is None or new_parent_id == "":
            role.parent_role_id = None
        else:
            if str(new_parent_id) == str(id):
                raise HTTPException(status_code=422, detail="A role cannot be its own parent.")
                
            p_res = await db.execute(select(Role).where(Role.id == new_parent_id, Role.deleted_at.is_(None)))
            if not p_res.scalar_one_or_none():
                raise HTTPException(status_code=404, detail="Parent role not found.")
                
            if await would_create_cycle(id, new_parent_id, db):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Updating parent role would create a cycle."
                )
            import uuid
            role.parent_role_id = uuid.UUID(str(new_parent_id))

    # Update other fields
    if payload.name is not None:
        cleaned_name = payload.name.strip()
        if not cleaned_name:
            raise HTTPException(status_code=400, detail="Role name cannot be empty.")
            
        if cleaned_name.lower() != role.name.lower():
            existing = await db.execute(
                select(Role)
                .where(func.lower(Role.name) == cleaned_name.lower(), Role.deleted_at.is_(None))
                .where(Role.id != id)
            )
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=400, detail=f"Role with name '{cleaned_name}' already exists.")
            role.name = cleaned_name

    if payload.color is not None:
        role.color = payload.color

    await db.flush()
    await recalculate_role_levels(db)
    await db.flush()
    await db.refresh(role)

    members_res = await db.execute(select(func.count(User.id)).where(User.role_id == role.id))
    member_count = members_res.scalar_one()

    return {
        "id": str(role.id),
        "name": role.name,
        "slug": role.slug,
        "level": role.level,
        "color": role.color,
        "is_system": role.is_system,
        "is_active": role.is_active,
        "parent_role_id": str(role.parent_role_id) if role.parent_role_id else None,
        "member_count": member_count
    }


@router.delete("/{id}")
async def delete_role(
    id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    """
    Soft delete a role. Superadmin only.
    """
    result = await db.execute(select(Role).where(Role.id == id, Role.deleted_at.is_(None)))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Block if system role
    if getattr(role, "is_system", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System roles cannot be modified."
        )

    # Block if users are assigned
    count_res = await db.execute(select(func.count(User.id)).where(User.role_id == id))
    user_count = count_res.scalar_one()
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete role with {user_count} assigned users."
        )

    # Dynamic check for permission junction tables
    from sqlalchemy import text
    for table_name in ["table_permission_roles", "connector_permission_roles"]:
        tbl_exists_res = await db.execute(
            text(
                "SELECT EXISTS (SELECT FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = :table_name)"
            ),
            {"table_name": table_name}
        )
        if tbl_exists_res.scalar():
            ref_res = await db.execute(
                text(f"SELECT count(*) FROM {table_name} WHERE role_id = :role_id"),
                {"role_id": id}
            )
            if ref_res.scalar() > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot delete role. It is referenced in permission table '{table_name}'."
                )

    # Soft Delete
    role.deleted_at = datetime.utcnow()
    role.is_active = False
    await db.flush()
    await recalculate_role_levels(db)
    await db.flush()

    return {"status": "success", "message": "Role soft-deleted successfully."}


@router.put("/users/{id}/manager")
async def assign_manager(
    id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    """
    Assign a manager to a user. Superadmin/Admin only.
    """
    manager_id = payload.get("manager_id")
    
    # Clear existing manager assignments for this member
    await db.execute(
        delete(UserManagerAssignment).where(UserManagerAssignment.member_user_id == id)
    )
    
    if manager_id:
        m_res = await db.execute(select(User).where(User.id == manager_id))
        if not m_res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Manager not found")
            
        if str(manager_id) == str(id):
            raise HTTPException(status_code=400, detail="A user cannot be their own manager.")
            
        db.add(UserManagerAssignment(
            manager_user_id=manager_id,
            member_user_id=id
        ))
        
    await db.flush()
    return {"status": "success", "message": "Manager assignment updated."}


@router.get("/users/{id}/members", response_model=List[UserOut])
async def get_managed_members(
    id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    """
    Get all members managed by a manager. Superadmin/Admin only.
    """
    stmt = (
        select(User)
        .options(selectinload(User.role_relation))
        .join(UserManagerAssignment, UserManagerAssignment.member_user_id == User.id)
        .where(UserManagerAssignment.manager_user_id == id)
    )
    res = await db.execute(stmt)
    return res.scalars().all()
