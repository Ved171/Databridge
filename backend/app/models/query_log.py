"""
app/models/query_log.py
-----------------------
QueryLog model for audit logging.
"""
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, gen_uuid


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
