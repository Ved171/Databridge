"""
app/models/packages.py
----------------------
Access Package models and all related junction/assignment tables.
"""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey,
    Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


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
