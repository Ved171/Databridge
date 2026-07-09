"""
app/models/roles.py
-------------------
Role model.
"""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Integer
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


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
