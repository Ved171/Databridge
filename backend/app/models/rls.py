"""
app/models/rls.py
-----------------
Row-Level Security policy models.
"""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey,
    Text, JSON, Enum as SAEnum, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, gen_uuid
from app.models.enums import UserRole


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


class RLSGlobalSetting(Base):
    """Key-value store for global RLS settings (e.g. kill switch)."""
    __tablename__ = 'rls_global_settings'

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    key        = Column(String, nullable=False, unique=True)
    value      = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
