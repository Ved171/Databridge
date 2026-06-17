from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError

from app.core.database import get_db
from app.core.security import decode_token
from app.models import User, WorkspaceMember, ConnectorPermission, UserRole, Role, Department, UserManagerAssignment
from sqlalchemy.orm import selectinload

from datetime import datetime

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

    result = await db.execute(
        select(User).options(selectinload(User.role_relation)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive or does not exist.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("token_version") != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superadmin:
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return current_user


ROLE_RANK = {"superadmin": 4, "super_admin": 4, "admin": 3, "workspace_admin": 2, "member": 1}

async def get_user_rank(user: User, db: AsyncSession) -> int:
    if user.is_superadmin:
        return 999
    if not user.role_id:
        return 1
    res = await db.execute(select(Role).where(Role.id == user.role_id))
    role = res.scalar_one_or_none()
    return role.level if role else 1


async def would_create_cycle(role_id: str, new_parent_id: str, db: AsyncSession) -> bool:
    current = new_parent_id
    for _ in range(20):
        if current is None:
            return False
        if str(current) == str(role_id):
            return True  # cycle detected
        res = await db.execute(
            select(Role.parent_role_id).where(Role.id == current)
        )
        current = res.scalar_one_or_none()
    return True  # treat max-depth hit as a cycle


async def resolve_role_chain(
    role_id: Optional[str],
    db: AsyncSession,
    max_depth: int = 10,
    _cache: Optional[dict] = None,
) -> list[str]:
    """
    Returns the role_id plus all descendant role IDs (roles that are junior to this role).
    Most specific (highest level/ancestor) first.
    Example: Manager inherits Member's permissions, so Manager returns [manager_id, member_id].
    """
    if not role_id:
        return []

    if _cache is not None and role_id in _cache:
        return _cache[role_id]

    chain = [str(role_id)]
    current_level = [str(role_id)]
    seen = {str(role_id)}

    for _ in range(max_depth):
        if not current_level:
            break
        res = await db.execute(
            select(Role.id)
            .where(Role.parent_role_id.in_(current_level), Role.deleted_at.is_(None))
        )
        next_level = [str(r) for r in res.scalars().all() if str(r) not in seen]
        if not next_level:
            break
        chain.extend(next_level)
        seen.update(next_level)
        current_level = next_level

    if _cache is not None:
        _cache[role_id] = chain
    return chain


async def resolve_department_chain(
    department_id: Optional[str],
    db: AsyncSession,
    max_depth: int = 10,
    _cache: Optional[dict] = None,
) -> list[str]:
    """
    Returns the department_id plus all ancestor department IDs up to root.
    Most specific first.
    Example: HR > Recruitment returns [recruitment_id, hr_id]
    """
    if not department_id:
        return []

    if _cache is not None and department_id in _cache:
        return _cache[department_id]

    chain = []
    current_id = department_id
    seen: set[str] = set()

    for _ in range(max_depth):
        if not current_id or current_id in seen:
            break
        seen.add(current_id)
        res = await db.execute(
            select(Department.id, Department.parent_department_id)
            .where(Department.id == current_id, Department.is_active == True)
        )
        row = res.one_or_none()
        if not row:
            break
        chain.append(str(row.id))
        current_id = row.parent_department_id

    if _cache is not None:
        _cache[department_id] = chain
    return chain


async def resolve_managed_users(
    manager_id: str,
    db: AsyncSession,
    max_depth: int = 5,
) -> list[str]:
    """
    Returns all user IDs directly or indirectly managed by manager_id.
    Used in F-08 RLS scoping — available here so F-07 can reference it.
    """
    all_members: set[str] = set()
    current_level = [manager_id]

    for _ in range(max_depth):
        if not current_level:
            break
        res = await db.execute(
            select(UserManagerAssignment.member_user_id)
            .where(UserManagerAssignment.manager_user_id.in_(current_level))
        )
        next_level = [str(r) for r in res.scalars().all() if str(r) not in all_members]
        all_members.update(next_level)
        current_level = next_level

    return list(all_members)


async def get_current_admin_or_wsadmin(current_user: User = Depends(get_current_user)) -> User:
    """Allow access if user is admin (superadmin) or workspace_admin."""
    if current_user.is_superadmin:
        return current_user
    role = getattr(current_user, "role", None) or "member"
    if role not in ("superadmin", "admin", "super_admin", "workspace_admin"):
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


def is_grant_active(row) -> bool:
    """
    Returns True if the grant is currently within its valid window
    and has not been manually revoked.
    Accepts any model with valid_from, expires_at, revoked_at fields.
    """
    now = datetime.utcnow()

    if getattr(row, 'revoked_at', None) is not None:
        return False
    if getattr(row, 'valid_from', None) is not None and now < row.valid_from:
        return False
    if getattr(row, 'expires_at', None) is not None and now > row.expires_at:
        return False

    return True


# ── PERMISSION RESOLUTION ORDER ───────────────────────────────────────────────
# 1. Superadmin          → always allow, skip all checks
# 2. Explicit deny       → dept chain deny OR direct role deny → immediately False
# 3. User-level allow    → direct grant to this specific user
# 4. Role allow          → exact role match (no hierarchy inheritance)
# 5. Dept chain allow    → user's dept or any ancestor dept
# 4.5 Package allow/deny → active packages assigned to user's dept/role
# 6. Default policy      → connector.default_policy == 'allow_all'
#
# Deny always wins. Package result (True/False/None) is checked after dept chain.
# None means no package rule matched — fall through to default policy.
# ─────────────────────────────────────────────────────────────────────────────

async def check_connector_permission(
    connector_id: str,
    operation: str,         # 'read' | 'create' | 'update' | 'delete'
    user: User,
    db: AsyncSession,
    _cache: Optional[dict] = None,
) -> bool:
    if user.is_superadmin:
        return True

    from app.models import (
        ConnectorPermissionDepartment, ConnectorPermissionRole, Connector, ConnectorPermission
    )
    from sqlalchemy import func
    
    flag = f"can_{operation}"
    role_chain = [str(user.role_id)] if user.role_id else []
    dept_chain = await resolve_department_chain(user.department_id, db, _cache=_cache)

    # ── 1. Explicit deny ──────────────────────────────────────────────
    if dept_chain:
        dept_deny_rows = await db.execute(
            select(ConnectorPermissionDepartment).join(ConnectorPermission)
            .where(
                ConnectorPermission.connector_id == connector_id,
                ConnectorPermissionDepartment.department_id.in_(dept_chain),
                ConnectorPermissionDepartment.is_deny == True,
            )
        )
        for row in dept_deny_rows.scalars():
            if is_grant_active(row):
                if row.role_id is None:
                    return False
                # Deny targets a specific role: only deny if user's role
                # exactly matches the denied role (no inheritance).
                if str(user.role_id) == str(row.role_id):
                    return False

    if role_chain:
        role_deny_rows = await db.execute(
            select(ConnectorPermissionRole).join(ConnectorPermission)
            .where(
                ConnectorPermission.connector_id == connector_id,
                ConnectorPermissionRole.role_id.in_(role_chain),
                ConnectorPermissionRole.is_deny == True,
            )
        )
        for row in role_deny_rows.scalars():
            if is_grant_active(row):
                return False

    # ── 2. User-level allow ───────────────────────────────────────────
    user_perm_rows = await db.execute(
        select(ConnectorPermission).where(
            ConnectorPermission.connector_id == connector_id,
            ConnectorPermission.user_id == str(user.id),
            getattr(ConnectorPermission, flag) == True,
        )
    )
    for row in user_perm_rows.scalars():
        if is_grant_active(row):
            return True

    # ── 3. Role chain allow ───────────────────────────────────────────
    if role_chain:
        role_allow_rows = await db.execute(
            select(ConnectorPermissionRole).join(ConnectorPermission)
            .where(
                ConnectorPermission.connector_id == connector_id,
                ConnectorPermissionRole.role_id.in_(role_chain),
                ConnectorPermissionRole.is_deny == False,
                getattr(ConnectorPermissionRole, flag) == True,
            )
        )
        for row in role_allow_rows.scalars():
            if is_grant_active(row):
                return True

    # ── 4. Department chain allow ─────────────────────────────────────
    if dept_chain:
        dept_allow_rows = await db.execute(
            select(ConnectorPermissionDepartment).join(ConnectorPermission)
            .where(
                ConnectorPermission.connector_id == connector_id,
                ConnectorPermissionDepartment.department_id.in_(dept_chain),
                ConnectorPermissionDepartment.is_deny == False,
                getattr(ConnectorPermissionDepartment, flag) == True,
            )
        )
        for row in dept_allow_rows.scalars():
            if is_grant_active(row):
                if row.role_id is None or str(row.role_id) in role_chain:
                    return True

    # ── 4.5. Package allow / deny ─────────────────────────────────────
    from app.core.packages import check_connector_via_package
    pkg_result = await check_connector_via_package(connector_id, operation, user, db)
    if pkg_result is not None:
        return pkg_result

    # ── 5. Default connector policy ───────────────────────────────────
    has_any_rules = await db.execute(
        select(func.count(ConnectorPermission.id)).where(
            ConnectorPermission.connector_id == connector_id
        )
    )
    connector = await db.get(Connector, connector_id)
    return has_any_rules.scalar() == 0 and connector.default_policy == 'allow_all'


def _table_name_matches(perm_tbl: str, target_tbl: str) -> bool:
    p = perm_tbl.lower().strip()
    t = target_tbl.lower().strip()
    if p == t:
        return True
    p_has_dot = "." in p
    t_has_dot = "." in t
    if p_has_dot != t_has_dot:
        p_bare = p.split(".")[-1]
        t_bare = t.split(".")[-1]
        return p_bare == t_bare
    return False


async def check_table_permission(
    connector_id: str,
    table_name: str,
    operation: str,         # 'read' | 'create' | 'update' | 'delete'
    user: User,
    db: AsyncSession,
    _cache: Optional[dict] = None,
) -> bool:
    if user.is_superadmin:
        return True

    connector_allowed = await check_connector_permission(
        connector_id,
        operation,
        user,
        db,
        _cache=_cache,
    )
    if not connector_allowed:
        return False

    from app.models import TablePermission, TablePermissionDepartment, TablePermissionRole, Connector, PackageTableRule
    from sqlalchemy import func

    # Fetch all table permissions for this connector
    cache_key = f"tp_conn_{connector_id}"
    if _cache is not None and cache_key in _cache:
        all_perms = _cache[cache_key]
    else:
        stmt = select(TablePermission).options(
            selectinload(TablePermission.departments),
            selectinload(TablePermission.roles)
        ).where(TablePermission.connector_id == connector_id)
        res = await db.execute(stmt)
        all_perms = res.scalars().all()
        if _cache is not None:
            _cache[cache_key] = all_perms
    
    # Check if any database rules are applicable to this user
    db_rules_cache_key = f"has_db_rules_{connector_id}_{user.id}"
    if _cache is not None and db_rules_cache_key in _cache:
        has_db_rules = _cache[db_rules_cache_key]
    else:
        has_db_rules = False
        role_chain = None
        dept_chain = None
        for tp in all_perms:
            if tp.applies_to_user_id is not None:
                if str(tp.applies_to_user_id) == str(user.id):
                    has_db_rules = True
                    break
            else:
                if role_chain is None:
                    role_chain = [str(user.role_id)] if user.role_id else []
                if dept_chain is None:
                    dept_chain = await resolve_department_chain(user.department_id, db, _cache=_cache)
                
                # Check if this rule applies via roles
                role_matched = False
                for r in tp.roles:
                    if str(r.role_id) in role_chain:
                        role_matched = True
                        break
                if role_matched:
                    has_db_rules = True
                    break
                    
                # Check if this rule applies via departments
                dept_matched = False
                for d in tp.departments:
                    if str(d.department_id) in dept_chain:
                        if d.role_id is not None:
                            if str(user.role_id) == str(d.role_id):
                                dept_matched = True
                                break
                        else:
                            dept_matched = True
                            break
                if dept_matched:
                    has_db_rules = True
                    break
        if _cache is not None:
            _cache[db_rules_cache_key] = has_db_rules

    # Check if there are any package table rules for this connector in the user's active packages
    pkg_cache_key = f"pkg_tp_conn_{connector_id}_{user.id}"
    if _cache is not None and pkg_cache_key in _cache:
        has_pkg_rules = _cache[pkg_cache_key]
    else:
        from app.core.packages import resolve_active_packages
        active_packs = await resolve_active_packages(user, db)
        if active_packs:
            active_pack_ids = [str(p.id) for p in active_packs]
            pkg_rules_stmt = select(func.count(PackageTableRule.id)).where(
                PackageTableRule.connector_id == connector_id,
                PackageTableRule.package_id.in_(active_pack_ids)
            )
            pkg_rules_res = await db.execute(pkg_rules_stmt)
            has_pkg_rules = pkg_rules_res.scalar() > 0
        else:
            has_pkg_rules = False
        if _cache is not None:
            _cache[pkg_cache_key] = has_pkg_rules

    has_table_rules = has_db_rules or has_pkg_rules

    # Use the flexible _table_name_matches helper to find rules for this specific table
    matched_perms = [p for p in all_perms if _table_name_matches(p.table_name, table_name)]

    conn_cache_key = f"connector_{connector_id}"
    if _cache is not None and conn_cache_key in _cache:
        connector = _cache[conn_cache_key]
    else:
        connector = await db.get(Connector, connector_id)
        if _cache is not None:
            _cache[conn_cache_key] = connector

    # If matched_perms exists, evaluate DB rules
    if matched_perms:
        matched_ids = [p.id for p in matched_perms]
        flag = f"can_{operation}"
        role_chain = [str(user.role_id)] if user.role_id else []
        dept_chain = await resolve_department_chain(user.department_id, db, _cache=_cache)

        # ── 1. Explicit deny — any source, checked first ──────────────────
        # Check dept chain deny
        if dept_chain:
            dept_deny = await db.execute(
                select(TablePermissionDepartment).join(TablePermission)
                .where(
                    TablePermission.id.in_(matched_ids),
                    TablePermissionDepartment.department_id.in_(dept_chain),
                    TablePermissionDepartment.is_deny == True,
                )
            )
            for row in dept_deny.scalars():
                if row.role_id is None:
                    return False
                if str(user.role_id) == str(row.role_id):
                    return False

        # Check role chain deny
        if role_chain:
            role_deny = await db.execute(
                select(TablePermissionRole).join(TablePermission)
                .where(
                    TablePermission.id.in_(matched_ids),
                    TablePermissionRole.role_id.in_(role_chain),
                    TablePermissionRole.is_deny == True,
                )
            )
            if role_deny.scalar_one_or_none():
                return False

        # ── 2. User-level allow ───────────────────────────────────────────
        user_perm = await db.execute(
            select(TablePermission).where(
                TablePermission.id.in_(matched_ids),
                TablePermission.applies_to_user_id == str(user.id),
                getattr(TablePermission, flag) == True,
            )
        )
        if user_perm.scalar_one_or_none():
            return True

        # ── 3. Role chain allow ───────────────────────────────────────────
        if role_chain:
            role_allow = await db.execute(
                select(TablePermissionRole).join(TablePermission)
                .where(
                    TablePermission.id.in_(matched_ids),
                    TablePermissionRole.role_id.in_(role_chain),
                    TablePermissionRole.is_deny == False,
                    getattr(TablePermissionRole, flag) == True,
                )
            )
            if role_allow.scalar_one_or_none():
                return True

        # ── 4. Department chain allow ─────────────────────────────────────
        if dept_chain:
            dept_allow = await db.execute(
                select(TablePermissionDepartment).join(TablePermission)
                .where(
                    TablePermission.id.in_(matched_ids),
                    TablePermissionDepartment.department_id.in_(dept_chain),
                    TablePermissionDepartment.is_deny == False,
                    getattr(TablePermissionDepartment, flag) == True,
                )
            )
            for row in dept_allow.scalars():
                if row.role_id is None or str(row.role_id) in role_chain:
                    return True

    # ── 4.5. Package allow / deny ─────────────────────────────────────
    from app.core.packages import check_table_via_package
    pkg_result = await check_table_via_package(connector_id, table_name, operation, user, db)
    if pkg_result is not None:
        return pkg_result

    # ── 5. Fallback ───────────────────────────────────────────────────
    # If any table rules exist for the connector, default behavior is DENY.
    # Otherwise, since connector-level permission is allowed, all tables are accessible.
    if has_table_rules:
        return False
    return True
