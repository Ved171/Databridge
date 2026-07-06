import uuid
from uuid import uuid4
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Integer,
    Text, JSON, Enum as SAEnum, UniqueConstraint, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


def gen_uuid():
    return str(uuid.uuid4())


#  Enums 

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    WORKSPACE_ADMIN = "workspace_admin"
    MEMBER = "member"
    VIEWER = "viewer"


class ConnectorType(str, enum.Enum):
    # Relational SQL
    POSTGRES      = "postgres"
    MYSQL         = "mysql"
    SQLITE        = "sqlite"
    MSSQL         = "mssql"
    ORACLE        = "oracle"
    SNOWFLAKE     = "snowflake"
    REDSHIFT      = "redshift"
    BIGQUERY      = "bigquery"
    # NoSQL / Document
    MONGODB       = "mongodb"
    ELASTICSEARCH = "elasticsearch"
    REDIS         = "redis"
    DYNAMODB      = "dynamodb"
    # SaaS / API
    SALESFORCE    = "salesforce"
    REST_API      = "rest_api"
    AIRTABLE      = "airtable"


class PermissionLevel(str, enum.Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"


#  Models 

class User(Base):
    __tablename__ = "users"

    id           = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email        = Column(String, unique=True, nullable=False, index=True)
    employee_code = Column(String, unique=True, nullable=True, index=True)
    name         = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_superadmin = Column(Boolean, default=False)
    role_id      = Column(UUID(as_uuid=True), ForeignKey('roles.id'), nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)
    department_id = Column(UUID(as_uuid=True), ForeignKey('departments.id'), nullable=True)

    force_password_change = Column(Boolean, default=True, nullable=False)
    token_version         = Column(Integer, default=1, nullable=False)
    is_active             = Column(Boolean, default=True, nullable=False)
    deleted_at            = Column(DateTime, nullable=True)

    workspace_memberships = relationship("WorkspaceMember", back_populates="user")
    query_logs            = relationship("QueryLog", back_populates="user")
    department            = relationship("Department", back_populates="members")
    role_relation         = relationship("Role", back_populates="members")

    @property
    def role(self) -> str:
        if self.is_superadmin:
            return "superadmin"
        if "role_relation" in self.__dict__:
            r = self.__dict__["role_relation"]
            if r:
                return r.slug
        return "member"


class Workspace(Base):
    __tablename__ = "workspaces"

    id          = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name        = Column(String, nullable=False)
    slug        = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)

    members     = relationship("WorkspaceMember", back_populates="workspace")
    connectors  = relationship("Connector", back_populates="workspace")


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)

    id           = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"))
    user_id      = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    role         = Column(SAEnum(UserRole), default=UserRole.MEMBER)
    joined_at    = Column(DateTime, default=datetime.utcnow)

    workspace    = relationship("Workspace", back_populates="members")
    user         = relationship("User", back_populates="workspace_memberships")


class Connector(Base):
    """
    One connector = one data source (one DB, one API, etc.)
    Credentials are AES-256 encrypted at rest.
    """
    __tablename__ = "connectors"

    id             = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    workspace_id   = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"))
    name           = Column(String, nullable=False)
    type           = Column(SAEnum(ConnectorType), nullable=False)
    # Encrypted JSON blob: {"host":..., "port":..., "user":..., "password":..., ...}
    encrypted_config = Column(Text, nullable=False)
    # Cached schema: {"tables": [{"name":"users","columns":[...]}]}
    schema_cache   = Column(JSON, nullable=True)
    schema_cached_at = Column(DateTime, nullable=True)
    is_active      = Column(Boolean, default=True)
    # Default policy: 'allow_all' | 'deny_all'
    # 'allow_all': existing connectors (backward compatible)
    # 'deny_all': new connectors (closed by default)
    default_policy = Column(String, nullable=False, default='deny_all')
    created_by     = Column(UUID(as_uuid=False), ForeignKey("users.id"))
    created_at     = Column(DateTime, default=datetime.utcnow)

    workspace      = relationship("Workspace", back_populates="connectors")
    permissions    = relationship("ConnectorPermission", back_populates="connector", cascade="all, delete-orphan")
    rls_policies   = relationship("RLSPolicy", back_populates="connector", cascade="all, delete-orphan")
    table_permissions = relationship("TablePermission", back_populates="connector", cascade="all, delete-orphan")

    @property
    def num_tables(self) -> int:
        if self.schema_cache and isinstance(self.schema_cache, dict):
            return len(self.schema_cache.get("tables", []))
        return 0



class ConnectorPermission(Base):
    """
    Per-user, per-connector CRUD permissions.
    A user has a tick box for each of: CREATE / READ / UPDATE / DELETE
    """
    __tablename__ = "connector_permissions"
    __table_args__ = (UniqueConstraint("connector_id", "user_id"),)

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    connector_id = Column(UUID(as_uuid=False), ForeignKey("connectors.id", ondelete="CASCADE"))
    user_id      = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))

    # Granular CRUD flags -- exactly like CData
    can_create   = Column(Boolean, default=False)
    can_read     = Column(Boolean, default=True)
    can_update   = Column(Boolean, default=False)
    can_delete   = Column(Boolean, default=False)

    granted_by   = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    granted_at   = Column(DateTime, default=datetime.utcnow)
    allow_share_access = Column(Boolean, default=False, nullable=False)
    granted_by_user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Time-bound access columns
    valid_from   = Column(DateTime, nullable=True)   # None = active immediately
    expires_at   = Column(DateTime, nullable=True)   # None = never expires
    revoked_at   = Column(DateTime, nullable=True)   # manual revocation
    revoked_by   = Column(UUID(as_uuid=False), ForeignKey('users.id'), nullable=True)
    grant_reason = Column(String, nullable=True)    # optional note for audit trail

    connector    = relationship("Connector", back_populates="permissions")
    user         = relationship("User", foreign_keys=[user_id])
    departments  = relationship("ConnectorPermissionDepartment", back_populates="connector_permission", cascade="all, delete-orphan")
    roles        = relationship("ConnectorPermissionRole", back_populates="connector_permission", cascade="all, delete-orphan")


class ConnectorPermissionDepartment(Base):
    """
    Junction table for granting connector-level access to entire departments.
    """
    __tablename__ = 'connector_permission_departments'
    id                     = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    connector_permission_id = Column(UUID(as_uuid=True), ForeignKey('connector_permissions.id', ondelete='CASCADE'), nullable=False)
    department_id          = Column(UUID(as_uuid=True), ForeignKey('departments.id', ondelete='CASCADE'), nullable=False)
    is_deny                = Column(Boolean, default=False, nullable=False)
    can_read               = Column(Boolean, default=True,  nullable=False)
    can_create             = Column(Boolean, default=False, nullable=False)
    can_update             = Column(Boolean, default=False, nullable=False)
    can_delete             = Column(Boolean, default=False, nullable=False)

    # Time-bound access columns
    valid_from   = Column(DateTime, nullable=True)
    expires_at   = Column(DateTime, nullable=True)
    revoked_at   = Column(DateTime, nullable=True)
    revoked_by   = Column(UUID(as_uuid=False), ForeignKey('users.id'), nullable=True)
    grant_reason = Column(String, nullable=True)

    role_id      = Column(UUID(as_uuid=True), ForeignKey('roles.id', ondelete='CASCADE'), nullable=True)

    __table_args__         = (UniqueConstraint('connector_permission_id', 'department_id', 'role_id'),)

    connector_permission = relationship("ConnectorPermission", back_populates="departments")
    department           = relationship("Department")
    role                 = relationship("Role")


class ConnectorPermissionRole(Base):
    """
    Junction table for granting connector-level access to entire roles.
    """
    __tablename__ = 'connector_permission_roles'
    id                     = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    connector_permission_id = Column(UUID(as_uuid=True), ForeignKey('connector_permissions.id', ondelete='CASCADE'), nullable=False)
    role_id                = Column(UUID(as_uuid=True), ForeignKey('roles.id', ondelete='CASCADE'), nullable=False)
    is_deny                = Column(Boolean, default=False, nullable=False)
    can_read               = Column(Boolean, default=True,  nullable=False)
    can_create             = Column(Boolean, default=False, nullable=False)
    can_update             = Column(Boolean, default=False, nullable=False)
    can_delete             = Column(Boolean, default=False, nullable=False)

    # Time-bound access columns
    valid_from   = Column(DateTime, nullable=True)
    expires_at   = Column(DateTime, nullable=True)
    revoked_at   = Column(DateTime, nullable=True)
    revoked_by   = Column(UUID(as_uuid=False), ForeignKey('users.id'), nullable=True)
    grant_reason = Column(String, nullable=True)

    __table_args__         = (UniqueConstraint('connector_permission_id', 'role_id'),)

    connector_permission = relationship("ConnectorPermission", back_populates="roles")
    role                 = relationship("Role")


class RLSPolicy(Base):
    """
    Row-Level Security policies per connector.
    A policy is a filter condition applied automatically to every query
    for a given user/role on a given table.

    For SQL connectors, use `filter_expr` (a SQL WHERE fragment).
    For NoSQL connectors, use `filter_expr_nosql` (a JSON filter object).
    At least one of the two must be provided.

    Supported placeholders (both formats accepted):
      Underscore:  {user_id}, {user_email}, {user_name}
      Dot:         {user.id}, {user.email}, {user.name}

    Example (SQL):
      filter_expr = "department_id = '{user_id}'"
      filter_expr = "Email = '{user_email}'"
    Example (MongoDB):
      filter_expr_nosql = {"field": "org_id", "op": "eq", "value": "{user.id}"}
    Example (Redis):
      filter_expr_nosql = {"key_pattern": "org:{user.id}:*"}
    """
    __tablename__ = "rls_policies"

    id           = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    connector_id = Column(UUID(as_uuid=False), ForeignKey("connectors.id", ondelete="CASCADE"))
    name         = Column(String, nullable=False)
    table_name   = Column(String, nullable=False)
    # SQL WHERE fragment, supports {user.id}, {user.email}, {user.metadata.X}
    filter_expr  = Column(Text, nullable=True)
    # NoSQL filter object (MongoDB $match, ES bool filter, Redis key pattern)
    filter_expr_nosql = Column(JSON, nullable=True)
    # Apply to: specific user, or a role
    applies_to_user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    applies_to_role    = Column(SAEnum(UserRole), nullable=True)
    is_active    = Column(Boolean, default=True)
    created_at   = Column(DateTime, default=datetime.utcnow)

    connector    = relationship("Connector", back_populates="rls_policies")


class QueryLog(Base):
    """Audit log of every NL query executed."""
    __tablename__ = "query_logs"

    id             = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id        = Column(UUID(as_uuid=False), ForeignKey("users.id"))
    connector_id   = Column(UUID(as_uuid=False), ForeignKey("connectors.id"), nullable=True)
    natural_language = Column(Text)
    generated_sql  = Column(Text)
    status         = Column(String)   # success | error | blocked
    error_message  = Column(Text, nullable=True)
    row_count      = Column(String, nullable=True)
    duration_ms    = Column(String, nullable=True)
    executed_at    = Column(DateTime, default=datetime.utcnow)

    user           = relationship("User", back_populates="query_logs")


class TablePermission(Base):
    """
    Per-table, per-user/role table permission rules.
    If rules are defined for a connector, it defaults to deny (users can only access specified tables).
    """
    __tablename__ = "table_permissions"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    connector_id = Column(UUID(as_uuid=False), ForeignKey("connectors.id", ondelete="CASCADE"), nullable=False)
    table_name   = Column(String, nullable=False)

    applies_to_user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)

    can_create   = Column(Boolean, default=False)
    can_read     = Column(Boolean, default=True)
    can_update   = Column(Boolean, default=False)
    can_delete   = Column(Boolean, default=False)

    created_at   = Column(DateTime, default=datetime.utcnow)
    granted_by_user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    connector    = relationship("Connector", back_populates="table_permissions")
    user         = relationship("User", foreign_keys=[applies_to_user_id])
    departments  = relationship("TablePermissionDepartment", back_populates="table_permission", cascade="all, delete-orphan")
    roles        = relationship("TablePermissionRole", back_populates="table_permission", cascade="all, delete-orphan")


class TablePermissionDepartment(Base):
    __tablename__ = 'table_permission_departments'
    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    table_permission_id = Column(UUID(as_uuid=True), ForeignKey('table_permissions.id', ondelete='CASCADE'), nullable=False)
    department_id       = Column(UUID(as_uuid=True), ForeignKey('departments.id', ondelete='CASCADE'), nullable=False)
    is_deny             = Column(Boolean, default=False, nullable=False)
    can_read            = Column(Boolean, default=True,  nullable=False)
    can_create          = Column(Boolean, default=False, nullable=False)
    can_update          = Column(Boolean, default=False, nullable=False)
    can_delete          = Column(Boolean, default=False, nullable=False)
    role_id             = Column(UUID(as_uuid=True), ForeignKey('roles.id', ondelete='CASCADE'), nullable=True)
    __table_args__      = (UniqueConstraint('table_permission_id', 'department_id', 'role_id'),)

    table_permission = relationship("TablePermission", back_populates="departments")
    department       = relationship("Department")
    role             = relationship("Role")


class TablePermissionRole(Base):
    __tablename__ = 'table_permission_roles'
    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    table_permission_id = Column(UUID(as_uuid=True), ForeignKey('table_permissions.id', ondelete='CASCADE'), nullable=False)
    role_id             = Column(UUID(as_uuid=True), ForeignKey('roles.id', ondelete='CASCADE'), nullable=False)
    is_deny             = Column(Boolean, default=False, nullable=False)
    can_read            = Column(Boolean, default=True,  nullable=False)
    can_create          = Column(Boolean, default=False, nullable=False)
    can_update          = Column(Boolean, default=False, nullable=False)
    can_delete          = Column(Boolean, default=False, nullable=False)
    __table_args__      = (UniqueConstraint('table_permission_id', 'role_id'),)

    table_permission = relationship("TablePermission", back_populates="roles")
    role             = relationship("Role")


class Role(Base):
    __tablename__ = 'roles'
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name           = Column(String, nullable=False, unique=True)
    slug           = Column(String, nullable=False, unique=True)  # immutable after creation
    level          = Column(Integer, nullable=False)              # higher = more privileged
    color          = Column(String, default='1E40AF')
    is_system      = Column(Boolean, default=False)               # true = not deletable via UI
    is_active      = Column(Boolean, default=True)
    deleted_at     = Column(DateTime, nullable=True)              # soft delete
    parent_role_id = Column(UUID(as_uuid=True), ForeignKey('roles.id'), nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)
    members        = relationship('User', back_populates='role_relation')


class Department(Base):
    __tablename__ = 'departments'
    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name              = Column(String, nullable=False, unique=True)
    slug              = Column(String, nullable=False, unique=True)  # immutable after creation
    color             = Column(String, default='1E40AF')             # hex, for UI badges
    is_active         = Column(Boolean, default=True)
    is_system         = Column(Boolean, default=False, nullable=False)
    default_role_id   = Column(UUID(as_uuid=True), ForeignKey('roles.id'), nullable=True)
    parent_department_id = Column(UUID(as_uuid=True), ForeignKey('departments.id'), nullable=True)
    created_at        = Column(DateTime, default=datetime.utcnow)
    members           = relationship('User', back_populates='department')


class UserManagerAssignment(Base):
    __tablename__ = 'user_manager_assignments'
    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    manager_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    member_user_id  = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    created_at      = Column(DateTime, default=datetime.utcnow)
    __table_args__  = (UniqueConstraint('manager_user_id', 'member_user_id'),)


class UserRoleHistory(Base):
    __tablename__ = 'user_role_history'
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    old_role_id = Column(UUID(as_uuid=True), ForeignKey('roles.id'), nullable=True)
    new_role_id = Column(UUID(as_uuid=True), ForeignKey('roles.id'), nullable=True)
    changed_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
    changed_by  = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)


class UserInviteToken(Base):
    __tablename__ = 'user_invite_tokens'
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    token_hash = Column(String, nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    used_at    = Column(DateTime, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)


class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    event_type  = Column(String, nullable=False)   # e.g. 'user.created', 'role.assigned'
    actor_id    = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    target_type = Column(String, nullable=True)    # 'user', 'department', 'role', 'permission'
    target_id   = Column(UUID(as_uuid=True), nullable=True)
    old_value   = Column(JSONB, nullable=True)
    new_value   = Column(JSONB, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)


class TableRLSFilter(Base):
    __tablename__ = 'table_rls_filters'
    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    connector_id        = Column(String, nullable=False)
    table_name          = Column(String, nullable=False)
    filter_expression   = Column(Text, nullable=False)
    # e.g. "EmployeeCode IN ({manager.managed_codes_quoted})"
    applies_to_role_id  = Column(UUID(as_uuid=True), ForeignKey('roles.id'), nullable=True)
    applies_to_dept_id  = Column(UUID(as_uuid=True), ForeignKey('departments.id'), nullable=True)
    applies_to_user_id  = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    is_active           = Column(Boolean, default=True, nullable=False)
    created_at          = Column(DateTime, default=datetime.utcnow)
    created_by          = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)

    __table_args__ = (
        # At least one target must be set
        CheckConstraint(
            "applies_to_role_id IS NOT NULL OR applies_to_dept_id IS NOT NULL OR applies_to_user_id IS NOT NULL",
            name='rls_filter_must_have_target'
        ),
    )


class AccessPackage(Base):
    __tablename__ = 'access_packages'
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name        = Column(String, nullable=False, unique=True)
    slug        = Column(String, nullable=False, unique=True)   # immutable after creation
    description = Column(Text, nullable=True)
    color       = Column(String, default='1E40AF')
    is_active   = Column(Boolean, default=True, nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)
    created_by  = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)

    # Contents
    connector_rules = relationship('PackageConnectorRule', back_populates='package', cascade='all, delete-orphan')
    table_rules     = relationship('PackageTableRule',     back_populates='package', cascade='all, delete-orphan')
    rls_filters     = relationship('PackageRLSFilter',     back_populates='package', cascade='all, delete-orphan')

    # Assignments
    dept_assignments = relationship('PackageDepartmentAssignment', back_populates='package', cascade='all, delete-orphan')
    role_assignments = relationship('PackageRoleAssignment',       back_populates='package', cascade='all, delete-orphan')


class PackageConnectorRule(Base):
    """Grants access to an entire connector via this package."""
    __tablename__ = 'package_connector_rules'
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    package_id = Column(UUID(as_uuid=True), ForeignKey('access_packages.id'), nullable=False)
    connector_id = Column(String, nullable=False)
    is_deny    = Column(Boolean, default=False, nullable=False)
    can_read   = Column(Boolean, default=True,  nullable=False)
    can_create = Column(Boolean, default=False, nullable=False)
    can_update = Column(Boolean, default=False, nullable=False)
    can_delete = Column(Boolean, default=False, nullable=False)
    package    = relationship('AccessPackage', back_populates='connector_rules')
    __table_args__ = (UniqueConstraint('package_id', 'connector_id'),)


class PackageTableRule(Base):
    """Grants access to a specific table via this package."""
    __tablename__ = 'package_table_rules'
    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    package_id   = Column(UUID(as_uuid=True), ForeignKey('access_packages.id'), nullable=False)
    connector_id = Column(String, nullable=False)
    table_name   = Column(String, nullable=False)
    is_deny      = Column(Boolean, default=False, nullable=False)
    can_read     = Column(Boolean, default=True,  nullable=False)
    can_create   = Column(Boolean, default=False, nullable=False)
    can_update   = Column(Boolean, default=False, nullable=False)
    can_delete   = Column(Boolean, default=False, nullable=False)
    package      = relationship('AccessPackage', back_populates='table_rules')
    __table_args__ = (UniqueConstraint('package_id', 'connector_id', 'table_name'),)


class PackageRLSFilter(Base):
    """Attaches an RLS filter expression to this package."""
    __tablename__ = 'package_rls_filters'
    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    package_id        = Column(UUID(as_uuid=True), ForeignKey('access_packages.id'), nullable=False)
    connector_id      = Column(String, nullable=False)
    table_name        = Column(String, nullable=False)
    filter_expression = Column(Text, nullable=False)
    package           = relationship('AccessPackage', back_populates='rls_filters')


class PackageDepartmentAssignment(Base):
    """Assigns a package to a department, optionally scoped to a specific role."""
    __tablename__ = 'package_department_assignments'
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    package_id    = Column(UUID(as_uuid=True), ForeignKey('access_packages.id'), nullable=False)
    department_id = Column(UUID(as_uuid=True), ForeignKey('departments.id'), nullable=False)
    role_id       = Column(UUID(as_uuid=True), ForeignKey('roles.id'), nullable=True)  # NULL = all roles in dept
    valid_from    = Column(DateTime, nullable=True)
    expires_at    = Column(DateTime, nullable=True)
    revoked_at    = Column(DateTime, nullable=True)
    revoked_by    = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    assigned_by   = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    assigned_at   = Column(DateTime, default=datetime.utcnow)
    package       = relationship('AccessPackage', back_populates='dept_assignments')
    __table_args__ = (UniqueConstraint('package_id', 'department_id', 'role_id'),)


class PackageRoleAssignment(Base):
    """Assigns a package to a role."""
    __tablename__ = 'package_role_assignments'
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    package_id  = Column(UUID(as_uuid=True), ForeignKey('access_packages.id'), nullable=False)
    role_id     = Column(UUID(as_uuid=True), ForeignKey('roles.id'), nullable=False)
    valid_from  = Column(DateTime, nullable=True)
    expires_at  = Column(DateTime, nullable=True)
    revoked_at  = Column(DateTime, nullable=True)
    revoked_by  = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    assigned_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    package     = relationship('AccessPackage', back_populates='role_assignments')
    __table_args__ = (UniqueConstraint('package_id', 'role_id'),)


class Notification(Base):
    """System and access notifications for users."""
    __tablename__ = "notifications"

    id         = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id    = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title      = Column(String, nullable=False)
    message    = Column(Text, nullable=False)
    is_read    = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user       = relationship("User", foreign_keys=[user_id])


class RLSGlobalSetting(Base):
    """Key-value store for global RLS settings (e.g. kill switch)."""
    __tablename__ = 'rls_global_settings'

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    key        = Column(String, nullable=False, unique=True)
    value      = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)