"""
app/models/connector.py
-----------------------
Connector model.
"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey,
    Text, JSON, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, gen_uuid
from app.models.enums import ConnectorType


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
