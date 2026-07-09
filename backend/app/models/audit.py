"""
app/models/audit.py
-------------------
AuditEvent model and Notification model.
"""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, gen_uuid


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
