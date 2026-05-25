from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any, Dict
from datetime import datetime
from app.models import UserRole, ConnectorType


# ─── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str


# ─── User ─────────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: str
    email: str
    name: str
    is_active: bool
    is_superadmin: bool
    role: str = "member"
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Workspace ────────────────────────────────────────────────────────────────

class WorkspaceCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None

class WorkspaceOut(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}

class AddMemberRequest(BaseModel):
    user_id: str
    role: UserRole = UserRole.MEMBER


# ─── Connector ────────────────────────────────────────────────────────────────

class ConnectorCreate(BaseModel):
    workspace_id: Optional[str] = None
    name: str
    type: ConnectorType
    config: Dict[str, Any]   # plain -- will be encrypted before storing

class ConnectorUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class ConnectorOut(BaseModel):
    id: str
    workspace_id: Optional[str]
    name: str
    type: ConnectorType
    is_active: bool
    schema_cached_at: Optional[datetime]
    created_at: datetime
    model_config = {"from_attributes": True}

class ConnectorSchemaOut(BaseModel):
    connector_id: str
    tables: List[Dict[str, Any]]


# ─── Permissions ──────────────────────────────────────────────────────────────

class PermissionUpsert(BaseModel):
    user_id: str
    can_create: bool = False
    can_read: bool = True
    can_update: bool = False
    can_delete: bool = False

class PermissionOut(BaseModel):
    id: str
    connector_id: str
    user_id: str
    can_create: bool
    can_read: bool
    can_update: bool
    can_delete: bool
    granted_at: datetime
    model_config = {"from_attributes": True}

class RLSPolicyCreate(BaseModel):
    name: str
    table_name: str
    filter_expr: str
    applies_to_user_id: Optional[str] = None
    applies_to_role: Optional[UserRole] = None

class RLSPolicyUpdate(BaseModel):
    name: Optional[str] = None
    table_name: Optional[str] = None
    filter_expr: Optional[str] = None
    applies_to_user_id: Optional[str] = None
    applies_to_role: Optional[UserRole] = None

class RLSPolicyOut(BaseModel):
    id: str
    connector_id: str
    name: str
    table_name: str
    filter_expr: str
    applies_to_user_id: Optional[str]
    applies_to_role: Optional[UserRole]
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Query ────────────────────────────────────────────────────────────────────

class NLQueryRequest(BaseModel):
    connector_id: Optional[str] = None
    question: str
    preview_only: bool = False
    execute_sql: Optional[str] = None

class NLQueryResponse(BaseModel):
    question: str
    generated_sql: str
    answer: str = ""
    history: List[Dict[str, Any]] = []
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    duration_ms: float
    blocked: bool = False
    block_reason: Optional[str] = None
    is_preview: bool = False

class QueryLogOut(BaseModel):
    id: str
    connector_id: Optional[str] = None
    natural_language: str
    generated_sql: Optional[str]
    status: str
    error_message: Optional[str]
    row_count: Optional[str]
    duration_ms: Optional[str]
    executed_at: datetime
    model_config = {"from_attributes": True}
