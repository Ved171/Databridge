from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_superadmin
from app.models import User, Workspace, WorkspaceMember, UserRole
from app.schemas import WorkspaceCreate, WorkspaceOut, AddMemberRequest

router = APIRouter()


@router.post("/", response_model=WorkspaceOut)
async def create_workspace(
    payload: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    existing = await db.execute(select(Workspace).where(Workspace.slug == payload.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Slug already taken")

    ws = Workspace(name=payload.name, slug=payload.slug, description=payload.description)
    db.add(ws)
    await db.flush()

    # Creator is workspace admin
    member = WorkspaceMember(workspace_id=ws.id, user_id=current_user.id, role=UserRole.WORKSPACE_ADMIN)
    db.add(member)
    await db.flush()
    await db.refresh(ws)
    return ws


@router.get("/", response_model=List[WorkspaceOut])
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_superadmin:
        result = await db.execute(select(Workspace).order_by(Workspace.name))
        return result.scalars().all()

    result = await db.execute(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == current_user.id)
    )
    return result.scalars().all()


@router.get("/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@router.post("/{workspace_id}/members")
async def add_member(
    workspace_id: str,
    payload: AddMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Only superadmin or workspace admin can add members
    if not current_user.is_superadmin:
        result = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == current_user.id,
                WorkspaceMember.role == UserRole.WORKSPACE_ADMIN,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Workspace admin required")

    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=payload.user_id,
        role=payload.role,
    )
    db.add(member)
    await db.flush()
    return {"status": "added"}


@router.get("/{workspace_id}/members")
async def list_members(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace_id)
    )
    rows = result.all()
    return [
        {
            "member_id": m.id,
            "user_id": u.id,
            "name": u.name,
            "email": u.email,
            "role": m.role,
            "joined_at": m.joined_at,
        }
        for m, u in rows
    ]
