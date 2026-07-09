"""
app/models/user.py
------------------
User, UserManagerAssignment, UserRoleHistory, UserInviteToken models.
"""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Integer,
    UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, gen_uuid


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
