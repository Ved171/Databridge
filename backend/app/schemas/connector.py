"""
app/schemas/connector.py
------------------------
Connector-related Pydantic schemas.
"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.enums import ConnectorType


class ConnectorCreate(BaseModel):
    workspace_id: Optional[str] = None
    name: str
    type: ConnectorType
    config: Dict[str, Any]   # plain -- will be encrypted before storing

class ConnectorUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class ConnectorPolicyUpdate(BaseModel):
    policy: str  # 'allow_all' | 'deny_all'

class ConnectorOut(BaseModel):
    id: str
    workspace_id: Optional[str]
    name: str
    type: ConnectorType
    is_active: bool
    default_policy: str  # 'allow_all' | 'deny_all'
    is_open_access: bool
    schema_cached_at: Optional[datetime]
    created_at: datetime
    num_tables: Optional[int] = 0
    model_config = {"from_attributes": True}

class ConnectorSchemaOut(BaseModel):
    connector_id: str
    tables: List[Dict[str, Any]]
