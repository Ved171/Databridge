import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey,
    Text, JSON, Enum as SAEnum, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


def gen_uuid():
    return str(uuid.uuid4())


# ─── Enums ────────────────────────────────────────────────────────────────────

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


# ─── Models ───────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id           = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email        = Column(String, unique=True, nullable=False, index=True)
    name         = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active    = Column(Boolean, default=True)
    is_superadmin = Column(Boolean, default=False)
    role         = Column(String, default="member")
    created_at   = Column(DateTime, default=datetime.utcnow)

    workspace_memberships = relationship("WorkspaceMember", back_populates="user")
    query_logs            = relationship("QueryLog", back_populates="user")


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
    created_by     = Column(UUID(as_uuid=False), ForeignKey("users.id"))
    created_at     = Column(DateTime, default=datetime.utcnow)

    workspace      = relationship("Workspace", back_populates="connectors")
    permissions    = relationship("ConnectorPermission", back_populates="connector", cascade="all, delete-orphan")
    rls_policies   = relationship("RLSPolicy", back_populates="connector", cascade="all, delete-orphan")


class ConnectorPermission(Base):
    """
    Per-user, per-connector CRUD permissions.
    A user has a tick box for each of: CREATE / READ / UPDATE / DELETE
    """
    __tablename__ = "connector_permissions"
    __table_args__ = (UniqueConstraint("connector_id", "user_id"),)

    id           = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    connector_id = Column(UUID(as_uuid=False), ForeignKey("connectors.id", ondelete="CASCADE"))
    user_id      = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))

    # Granular CRUD flags -- exactly like CData
    can_create   = Column(Boolean, default=False)
    can_read     = Column(Boolean, default=True)
    can_update   = Column(Boolean, default=False)
    can_delete   = Column(Boolean, default=False)

    granted_by   = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    granted_at   = Column(DateTime, default=datetime.utcnow)

    connector    = relationship("Connector", back_populates="permissions")
    user         = relationship("User", foreign_keys=[user_id])


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