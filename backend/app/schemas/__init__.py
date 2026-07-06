from pydantic import BaseModel, EmailStr, field_validator, computed_field, model_validator
from typing import Optional, List, Any, Dict
from datetime import datetime
from app.models import UserRole, ConnectorType



#  Auth 

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str


#  User 

class CreateUserRequest(BaseModel):
    name: str
    email: str
    department_id: str
    role_id: str

class AcceptInviteRequest(BaseModel):
    token: str
    password: str
    confirm_password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

class UserOut(BaseModel):
    id: str
    email: str
    name: str
    is_active: bool
    is_superadmin: bool
    force_password_change: bool
    department_id: Optional[str] = None
    role_id: Optional[str] = None
    role: str = "member"
    created_at: datetime
    model_config = {"from_attributes": True}

    @field_validator('role', mode='before')
    @classmethod
    def validate_role(cls, role: Any) -> str:
        if not role:
            return "member"
        if isinstance(role, str):
            return role
        try:
            return role.slug
        except Exception:
            return "member"

    @field_validator('role_id', 'department_id', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)


#  Workspace 

class WorkspaceCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None

class WorkspaceOut(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}

class AddMemberRequest(BaseModel):
    user_id: str
    role: UserRole = UserRole.MEMBER


#  Connector 

class ConnectorCreate(BaseModel):
    workspace_id: Optional[str] = None
    name: str
    type: ConnectorType
    config: Dict[str, Any]   # plain -- will be encrypted before storing

class ConnectorUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class ConnectorPolicyUpdate(BaseModel):
    policy: str  # 'allow_all' | 'deny_all'

class ConnectorOut(BaseModel):
    id: str
    workspace_id: Optional[str]
    name: str
    type: ConnectorType
    is_active: bool
    default_policy: str  # 'allow_all' | 'deny_all'
    is_open_access: bool
    schema_cached_at: Optional[datetime]
    created_at: datetime
    num_tables: Optional[int] = 0
    model_config = {"from_attributes": True}

class ConnectorSchemaOut(BaseModel):
    connector_id: str
    tables: List[Dict[str, Any]]


#  Permissions 

class PermissionUpsert(BaseModel):
    user_id: str
    can_create: bool = False
    can_read: bool = True
    can_update: bool = False
    can_delete: bool = False
    allow_share_access: bool = False
    valid_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    grant_reason: Optional[str] = None

class PermissionOut(BaseModel):
    id: str
    connector_id: str
    user_id: str
    can_create: bool
    can_read: bool
    can_update: bool
    can_delete: bool
    allow_share_access: bool = False
    granted_at: datetime
    valid_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    grant_reason: Optional[str] = None
    model_config = {"from_attributes": True}

    @field_validator('id', 'connector_id', 'user_id', 'revoked_by', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)

    @computed_field
    @property
    def is_active(self) -> bool:
        now = datetime.utcnow()
        if self.revoked_at is not None:
            return False
        if self.valid_from is not None and now < self.valid_from:
            return False
        if self.expires_at is not None and now > self.expires_at:
            return False
        return True

class GrantWindow(BaseModel):
    valid_from:   Optional[datetime] = None   # None = immediately
    expires_at:   Optional[datetime] = None   # None = never
    grant_reason: Optional[str] = None

class ConnectorPermissionCreate(BaseModel):
    connector_id: str
    user_id: str
    can_read:   bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False
    window: GrantWindow = GrantWindow()       # optional, defaults to open-ended

class ConnectorPermissionOut(BaseModel):
    id: str
    connector_id: str
    user_id: str
    valid_from:   Optional[datetime] = None
    expires_at:   Optional[datetime] = None
    revoked_at:   Optional[datetime] = None
    grant_reason: Optional[str] = None
    model_config = {"from_attributes": True}

    @field_validator('id', 'connector_id', 'user_id', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)

    @computed_field
    @property
    def is_active(self) -> bool:
        now = datetime.utcnow()
        if self.revoked_at is not None:
            return False
        if self.valid_from is not None and now < self.valid_from:
            return False
        if self.expires_at is not None and now > self.expires_at:
            return False
        return True

class RLSPolicyCreate(BaseModel):
    name: str
    table_name: str
    filter_expr: Optional[str] = None          # SQL WHERE fragment (for SQL connectors)
    filter_expr_nosql: Optional[Dict] = None   # JSON filter (for NoSQL connectors)
    applies_to_user_id: Optional[str] = None
    applies_to_role: Optional[UserRole] = None

class RLSPolicyUpdate(BaseModel):
    name: Optional[str] = None
    table_name: Optional[str] = None
    filter_expr: Optional[str] = None
    filter_expr_nosql: Optional[Dict] = None
    applies_to_user_id: Optional[str] = None
    applies_to_role: Optional[UserRole] = None

class RLSPolicyOut(BaseModel):
    id: str
    connector_id: str
    name: str
    table_name: str
    filter_expr: Optional[str] = None
    filter_expr_nosql: Optional[Dict] = None
    applies_to_user_id: Optional[str]
    applies_to_role: Optional[UserRole]
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class DeptPermissionEntry(BaseModel):
    department_id: str
    role_id: Optional[str] = None
    is_deny: bool = False
    can_read: bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False
    model_config = {"from_attributes": True}

    @field_validator('department_id', mode='before')
    @classmethod
    def validate_uuid(cls, val: Any) -> str:
        return str(val)

    @field_validator('role_id', mode='before')
    @classmethod
    def validate_role_id(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)


class RolePermissionEntry(BaseModel):
    role_id: str
    is_deny: bool = False
    can_read: bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False
    model_config = {"from_attributes": True}

    @field_validator('role_id', mode='before')
    @classmethod
    def validate_uuid(cls, val: Any) -> str:
        return str(val)


class ConnectorDeptPermissionEntry(BaseModel):
    """Entry for granting connector-level access to a department."""
    id: Optional[str] = None
    department_id: str
    role_id: Optional[str] = None
    is_deny: bool = False
    can_read: bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False
    valid_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    grant_reason: Optional[str] = None
    model_config = {"from_attributes": True}

    @computed_field
    @property
    def is_active(self) -> bool:
        now = datetime.utcnow()
        if self.revoked_at is not None:
            return False
        if self.valid_from is not None and now < self.valid_from:
            return False
        if self.expires_at is not None and now > self.expires_at:
            return False
        return True

    @field_validator('department_id', mode='before')
    @classmethod
    def validate_uuid(cls, val: Any) -> str:
        return str(val)

    @field_validator('id', 'revoked_by', 'role_id', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)


class ConnectorRolePermissionEntry(BaseModel):
    """Entry for granting connector-level access to a role."""
    id: Optional[str] = None
    role_id: str
    is_deny: bool = False
    can_read: bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False
    valid_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    grant_reason: Optional[str] = None
    model_config = {"from_attributes": True}

    @computed_field
    @property
    def is_active(self) -> bool:
        now = datetime.utcnow()
        if self.revoked_at is not None:
            return False
        if self.valid_from is not None and now < self.valid_from:
            return False
        if self.expires_at is not None and now > self.expires_at:
            return False
        return True

    @field_validator('role_id', mode='before')
    @classmethod
    def validate_uuid(cls, val: Any) -> str:
        return str(val)

    @field_validator('id', 'revoked_by', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)


class ConnectorPermissionBulkUpdate(BaseModel):
    """Bulk update for connector-level department and role permissions."""
    departments: List[ConnectorDeptPermissionEntry] = []
    roles: List[ConnectorRolePermissionEntry] = []


class ConnectorPermissionGroupedOut(BaseModel):
    """Display connector permissions grouped by user, department, and role."""
    connector_id: str
    user_grants: List[dict]  # existing per-user rows
    department_grants: List[ConnectorDeptPermissionEntry]
    role_grants: List[ConnectorRolePermissionEntry]
    model_config = {"from_attributes": True}


class TablePermissionCreate(BaseModel):
    connector_id: str
    table_name: str
    applies_to_user_id: Optional[str] = None
    departments: List[DeptPermissionEntry] = []
    roles: List[RolePermissionEntry] = []
    can_read: bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False


class TablePermissionOut(BaseModel):
    id: str
    connector_id: str
    table_name: str
    applies_to_user_id: Optional[str] = None
    departments: List[DeptPermissionEntry] = []
    roles: List[RolePermissionEntry] = []
    can_read: bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False
    is_package_rule: Optional[bool] = False
    model_config = {"from_attributes": True}

    @field_validator('id', 'connector_id', 'applies_to_user_id', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)



#  Query 

class NLQueryRequest(BaseModel):
    connector_id: Optional[str] = None
    question: str
    preview_only: bool = False
    execute_sql: Optional[str] = None

class NLQueryResponse(BaseModel):
    question: str
    generated_sql: str
    answer: str = ""
    history: List[Dict[str, Any]] = []
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    duration_ms: float
    blocked: bool = False
    block_reason: Optional[str] = None
    is_preview: bool = False

class QueryLogOut(BaseModel):
    id: str
    connector_id: Optional[str] = None
    natural_language: str
    generated_sql: Optional[str]
    status: str
    error_message: Optional[str]
    row_count: Optional[str]
    duration_ms: Optional[str]
    executed_at: datetime
    model_config = {"from_attributes": True}


#  Department 

class DepartmentCreate(BaseModel):
    name: str
    color: str = '1E40AF'
    default_role_id: Optional[str] = None
    parent_department_id: Optional[str] = None

class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None
    default_role_id: Optional[str] = None

class DepartmentOut(BaseModel):
    id: str
    name: str
    slug: str
    color: str
    is_active: bool
    is_system: bool = False
    default_role_id: Optional[str]
    parent_department_id: Optional[str]
    member_count: int
    model_config = {"from_attributes": True}

    @field_validator('id', 'default_role_id', 'parent_department_id', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)


#  Role 

class RoleCreate(BaseModel):
    name: str
    color: str = '1E40AF'
    level: Optional[int] = 1
    parent_role_id: Optional[str] = None

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    level: Optional[int] = None
    parent_role_id: Optional[str] = None

class RoleOut(BaseModel):
    id: str
    name: str
    slug: str
    level: int
    color: str
    is_system: bool
    is_active: bool
    parent_role_id: Optional[str]
    member_count: int
    model_config = {"from_attributes": True}

    @field_validator('id', 'parent_role_id', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)

class RoleTreeNode(BaseModel):
    id: str
    name: str
    level: int
    member_count: int = 0
    color: str = '1E40AF'
    is_system: bool = False
    is_active: bool = True
    children: List['RoleTreeNode'] = []

    @field_validator('id', mode='before')
    @classmethod
    def validate_uuid(cls, val: Any) -> str:
        return str(val)


#  RLS Filters 

class RLSFilterCreate(BaseModel):
    connector_id:       str
    table_name:         str
    filter_expression:  str
    applies_to_role_id: Optional[str] = None
    applies_to_dept_id: Optional[str] = None
    applies_to_user_id: Optional[str] = None

    @field_validator('filter_expression')
    @classmethod
    def must_contain_placeholder(cls, v: str) -> str:
        import re
        if not re.search(r'\{[\w.]+\}', v):
            raise ValueError("filter_expression must contain at least one {placeholder}.")
        return v

    @model_validator(mode='after')
    def must_have_target(self) -> 'RLSFilterCreate':
        if not any([self.applies_to_role_id, self.applies_to_dept_id, self.applies_to_user_id]):
            raise ValueError("At least one of applies_to_role_id, applies_to_dept_id, applies_to_user_id must be set.")
        return self


class RLSFilterOut(BaseModel):
    id:                 str
    connector_id:       str
    table_name:         str
    filter_expression:  str
    applies_to_role_id: Optional[str] = None
    applies_to_dept_id: Optional[str] = None
    applies_to_user_id: Optional[str] = None
    is_active:          bool
    created_at:         datetime
    is_package_rule:    Optional[bool] = False
    model_config = {"from_attributes": True}

    @field_validator('id', 'applies_to_role_id', 'applies_to_dept_id', 'applies_to_user_id', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)


class RLSContextOut(BaseModel):
    """What the debug endpoint returns -- shows resolved placeholder values."""
    user_id:                  str
    user_email:               str
    user_employee_code:       Optional[str] = None
    managed_codes:            List[str]
    managed_user_ids:         List[str]
    managed_count:            int
    is_manager:               bool


#  Access Packages 

class PackageConnectorRuleIn(BaseModel):
    connector_id: str
    is_deny:    bool = False
    can_read:   bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False
    model_config = {"from_attributes": True}

class PackageTableRuleIn(BaseModel):
    connector_id:     str
    table_name:       str
    is_deny:          bool = False
    can_read:         bool = True
    can_create:       bool = False
    can_update:       bool = False
    can_delete:       bool = False
    model_config = {"from_attributes": True}

class PackageRLSFilterIn(BaseModel):
    connector_id:     str
    table_name:       str
    filter_expression: str
    model_config = {"from_attributes": True}

class PackageCreate(BaseModel):
    name:              str
    description:       Optional[str] = None
    color:             str = '1E40AF'
    connector_rules:   List[PackageConnectorRuleIn] = []
    table_rules:       List[PackageTableRuleIn] = []
    rls_filters:       List[PackageRLSFilterIn] = []

class DeptRoleAssignmentIn(BaseModel):
    """Assigns a package to a specific role within a department."""
    department_id: str
    role_id: str

class PackageAssignIn(BaseModel):
    department_ids: List[str] = []
    role_ids:       List[str] = []
    dept_role_assignments: List[DeptRoleAssignmentIn] = []  # combined dept+role
    valid_from:     Optional[datetime] = None
    expires_at:     Optional[datetime] = None

class PackageDeptAssignmentOut(BaseModel):
    id: str
    department_id: str
    role_id: Optional[str] = None
    valid_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    assigned_by: str
    assigned_at: datetime
    model_config = {"from_attributes": True}

    @field_validator('id', 'department_id', 'role_id', 'revoked_by', 'assigned_by', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)

class PackageRoleAssignmentOut(BaseModel):
    id: str
    role_id: str
    valid_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    assigned_by: str
    assigned_at: datetime
    model_config = {"from_attributes": True}

    @field_validator('id', 'role_id', 'revoked_by', 'assigned_by', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)

class PackageOut(BaseModel):
    id:              str
    name:            str
    slug:            str
    description:     Optional[str]
    color:           str
    is_active:       bool
    connector_rules: List[PackageConnectorRuleIn]
    table_rules:     List[PackageTableRuleIn]
    rls_filters:     List[PackageRLSFilterIn]
    dept_assignments: List[PackageDeptAssignmentOut]
    role_assignments: List[PackageRoleAssignmentOut]
    created_at:      datetime
    model_config = {"from_attributes": True}

    @field_validator('id', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)


class NotificationOut(BaseModel):
    id: str
    user_id: str
    title: str
    message: str
    is_read: bool
    created_at: datetime
    model_config = {"from_attributes": True}

    @field_validator('id', 'user_id', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)




