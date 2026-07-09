"""
app/models/workspace.py
-----------------------
Workspace and WorkspaceMember models.
"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey,
    Text, Enum as SAEnum, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, gen_uuid
from app.models.enums import UserRole


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
