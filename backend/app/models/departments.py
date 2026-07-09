"""
app/models/departments.py
-------------------------
Department model.
"""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


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
