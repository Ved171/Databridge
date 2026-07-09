"""
app/models/__init__.py
----------------------
Re-exports all models and enums from domain-specific sub-modules.

All existing imports like `from app.models import User, Connector, ...`
continue to work unchanged.
"""

# ─── Enums ────────────────────────────────────────────────────────────────────
from app.models.enums import UserRole, ConnectorType, PermissionLevel  # noqa: F401

# ─── Base helpers ─────────────────────────────────────────────────────────────
from app.models.base import gen_uuid  # noqa: F401

# ─── User ─────────────────────────────────────────────────────────────────────
from app.models.user import (  # noqa: F401
    User,
    UserManagerAssignment,
    UserRoleHistory,
    UserInviteToken,
)

# ─── Workspace ────────────────────────────────────────────────────────────────
from app.models.workspace import Workspace, WorkspaceMember  # noqa: F401

# ─── Connector ────────────────────────────────────────────────────────────────
from app.models.connector import Connector  # noqa: F401

# ─── Permissions ──────────────────────────────────────────────────────────────
from app.models.permissions import (  # noqa: F401
    ConnectorPermission,
    ConnectorPermissionDepartment,
    ConnectorPermissionRole,
    TablePermission,
    TablePermissionDepartment,
    TablePermissionRole,
)

# ─── RLS ──────────────────────────────────────────────────────────────────────
from app.models.rls import (  # noqa: F401
    RLSPolicy,
    TableRLSFilter,
    RLSGlobalSetting,
)

# ─── Roles ────────────────────────────────────────────────────────────────────
from app.models.roles import Role  # noqa: F401

# ─── Departments ──────────────────────────────────────────────────────────────
from app.models.departments import Department  # noqa: F401

# ─── Query Log ────────────────────────────────────────────────────────────────
from app.models.query_log import QueryLog  # noqa: F401

# ─── Access Packages ─────────────────────────────────────────────────────────
from app.models.packages import (  # noqa: F401
    AccessPackage,
    PackageConnectorRule,
    PackageTableRule,
    PackageRLSFilter,
    PackageDepartmentAssignment,
    PackageRoleAssignment,
)

# ─── Audit & Notifications ───────────────────────────────────────────────────
from app.models.audit import AuditEvent, Notification  # noqa: F401