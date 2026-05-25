from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError

from app.core.database import get_db
from app.core.security import decode_token
from app.models import User, WorkspaceMember, ConnectorPermission, UserRole

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exception
    return user


async def get_current_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superadmin:
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return current_user


ROLE_RANK = {"superadmin": 4, "super_admin": 4, "admin": 3, "workspace_admin": 2, "member": 1}

def get_user_rank(user: User) -> int:
    if user.is_superadmin:
        return 4
    return ROLE_RANK.get(user.role or "member", 1)


async def get_current_admin_or_wsadmin(current_user: User = Depends(get_current_user)) -> User:
    """Allow access if user is admin (superadmin) or workspace_admin."""
    if current_user.is_superadmin:
        return current_user
    role = getattr(current_user, "role", None) or "member"
    if role not in ("admin", "super_admin", "workspace_admin"):
        raise HTTPException(status_code=403, detail="Admin or workspace admin access required")
    return current_user


async def require_workspace_admin(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    if current_user.is_superadmin:
        return current_user
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user.id,
            WorkspaceMember.role.in_([UserRole.WORKSPACE_ADMIN, UserRole.SUPER_ADMIN]),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Workspace admin access required")
    return current_user


async def check_connector_permission(
    connector_id: str,
    operation: str,  # read | create | update | delete
    current_user: User,
    db: AsyncSession,
) -> bool:
    """
    Check if a user has permission to perform an operation on a connector.
    Superadmins always have full access.
    """
    if current_user.is_superadmin:
        return True

    result = await db.execute(
        select(ConnectorPermission).where(
            ConnectorPermission.connector_id == connector_id,
            ConnectorPermission.user_id == current_user.id,
        )
    )
    perm = result.scalar_one_or_none()
    if not perm:
        return False

    return {
        "read":   perm.can_read,
        "create": perm.can_create,
        "update": perm.can_update,
        "delete": perm.can_delete,
    }.get(operation, False)
