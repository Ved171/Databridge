"""
app/models/permissions.py
-------------------------
Connector-level and table-level permission models with department/role junction tables.
"""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey,
    UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


# ─── Connector-Level Permissions ──────────────────────────────────────────────

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


# ─── Table-Level Permissions ─────────────────────────────────────────────────

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
