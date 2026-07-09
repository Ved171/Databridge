"""
app/schemas/__init__.py
-----------------------
Re-exports all Pydantic schemas from domain-specific sub-modules.

All existing imports like `from app.schemas import UserOut, ConnectorOut, ...`
continue to work unchanged.
"""

# ─── User & Auth ──────────────────────────────────────────────────────────────
from app.schemas.user import (  # noqa: F401
    LoginRequest,
    TokenResponse,
    RegisterRequest,
    CreateUserRequest,
    AcceptInviteRequest,
    ChangePasswordRequest,
    UserOut,
)

# ─── Workspace ────────────────────────────────────────────────────────────────
from app.schemas.workspace import (  # noqa: F401
    WorkspaceCreate,
    WorkspaceOut,
    AddMemberRequest,
)

# ─── Connector ────────────────────────────────────────────────────────────────
from app.schemas.connector import (  # noqa: F401
    ConnectorCreate,
    ConnectorUpdate,
    ConnectorPolicyUpdate,
    ConnectorOut,
    ConnectorSchemaOut,
)

# ─── Permissions ──────────────────────────────────────────────────────────────
from app.schemas.permissions import (  # noqa: F401
    PermissionUpsert,
    PermissionOut,
    GrantWindow,
    ConnectorPermissionCreate,
    ConnectorPermissionOut,
    DeptPermissionEntry,
    RolePermissionEntry,
    ConnectorDeptPermissionEntry,
    ConnectorRolePermissionEntry,
    ConnectorPermissionBulkUpdate,
    ConnectorPermissionGroupedOut,
    TablePermissionCreate,
    TablePermissionOut,
)

# ─── RLS ──────────────────────────────────────────────────────────────────────
from app.schemas.rls import (  # noqa: F401
    RLSPolicyCreate,
    RLSPolicyUpdate,
    RLSPolicyOut,
    RLSFilterCreate,
    RLSFilterOut,
    RLSContextOut,
)

# ─── Query ────────────────────────────────────────────────────────────────────
from app.schemas.query import (  # noqa: F401
    NLQueryRequest,
    NLQueryResponse,
    QueryLogOut,
)

# ─── Departments ──────────────────────────────────────────────────────────────
from app.schemas.departments import (  # noqa: F401
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentOut,
)

# ─── Roles ────────────────────────────────────────────────────────────────────
from app.schemas.roles import (  # noqa: F401
    RoleCreate,
    RoleUpdate,
    RoleOut,
    RoleTreeNode,
)

# ─── Packages ─────────────────────────────────────────────────────────────────
from app.schemas.packages import (  # noqa: F401
    PackageConnectorRuleIn,
    PackageTableRuleIn,
    PackageRLSFilterIn,
    PackageCreate,
    DeptRoleAssignmentIn,
    PackageAssignIn,
    PackageDeptAssignmentOut,
    PackageRoleAssignmentOut,
    PackageOut,
)

# ─── Notifications ────────────────────────────────────────────────────────────
from app.schemas.notifications import NotificationOut  # noqa: F401
