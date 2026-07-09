"""
app/schemas/permissions.py
--------------------------
All permission-related Pydantic schemas (connector-level, table-level, grouped).
"""
from pydantic import BaseModel, field_validator, computed_field
from typing import Optional, List, Any
from datetime import datetime
from app.models.enums import UserRole


# ─── Base Permission Schemas ─────────────────────────────────────────────────

class PermissionUpsert(BaseModel):
    user_id: str
    can_create: bool = False
    can_read: bool = True
    can_update: bool = False
    can_delete: bool = False
    allow_share_access: bool = False
    valid_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    grant_reason: Optional[str] = None

class PermissionOut(BaseModel):
    id: str
    connector_id: str
    user_id: str
    can_create: bool
    can_read: bool
    can_update: bool
    can_delete: bool
    allow_share_access: bool = False
    granted_at: datetime
    valid_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    grant_reason: Optional[str] = None
    model_config = {"from_attributes": True}

    @field_validator('id', 'connector_id', 'user_id', 'revoked_by', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)

    @computed_field
    @property
    def is_active(self) -> bool:
        now = datetime.utcnow()
        if self.revoked_at is not None:
            return False
        if self.valid_from is not None and now < self.valid_from:
            return False
        if self.expires_at is not None and now > self.expires_at:
            return False
        return True

class GrantWindow(BaseModel):
    valid_from:   Optional[datetime] = None   # None = immediately
    expires_at:   Optional[datetime] = None   # None = never
    grant_reason: Optional[str] = None

class ConnectorPermissionCreate(BaseModel):
    connector_id: str
    user_id: str
    can_read:   bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False
    window: GrantWindow = GrantWindow()       # optional, defaults to open-ended

class ConnectorPermissionOut(BaseModel):
    id: str
    connector_id: str
    user_id: str
    valid_from:   Optional[datetime] = None
    expires_at:   Optional[datetime] = None
    revoked_at:   Optional[datetime] = None
    grant_reason: Optional[str] = None
    model_config = {"from_attributes": True}

    @field_validator('id', 'connector_id', 'user_id', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)

    @computed_field
    @property
    def is_active(self) -> bool:
        now = datetime.utcnow()
        if self.revoked_at is not None:
            return False
        if self.valid_from is not None and now < self.valid_from:
            return False
        if self.expires_at is not None and now > self.expires_at:
            return False
        return True


# ─── Department & Role Permission Entries ────────────────────────────────────

class DeptPermissionEntry(BaseModel):
    department_id: str
    role_id: Optional[str] = None
    is_deny: bool = False
    can_read: bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False
    model_config = {"from_attributes": True}

    @field_validator('department_id', mode='before')
    @classmethod
    def validate_uuid(cls, val: Any) -> str:
        return str(val)

    @field_validator('role_id', mode='before')
    @classmethod
    def validate_role_id(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)


class RolePermissionEntry(BaseModel):
    role_id: str
    is_deny: bool = False
    can_read: bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False
    model_config = {"from_attributes": True}

    @field_validator('role_id', mode='before')
    @classmethod
    def validate_uuid(cls, val: Any) -> str:
        return str(val)


class ConnectorDeptPermissionEntry(BaseModel):
    """Entry for granting connector-level access to a department."""
    id: Optional[str] = None
    department_id: str
    role_id: Optional[str] = None
    is_deny: bool = False
    can_read: bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False
    valid_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    grant_reason: Optional[str] = None
    model_config = {"from_attributes": True}

    @computed_field
    @property
    def is_active(self) -> bool:
        now = datetime.utcnow()
        if self.revoked_at is not None:
            return False
        if self.valid_from is not None and now < self.valid_from:
            return False
        if self.expires_at is not None and now > self.expires_at:
            return False
        return True

    @field_validator('department_id', mode='before')
    @classmethod
    def validate_uuid(cls, val: Any) -> str:
        return str(val)

    @field_validator('id', 'revoked_by', 'role_id', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)


class ConnectorRolePermissionEntry(BaseModel):
    """Entry for granting connector-level access to a role."""
    id: Optional[str] = None
    role_id: str
    is_deny: bool = False
    can_read: bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False
    valid_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    grant_reason: Optional[str] = None
    model_config = {"from_attributes": True}

    @computed_field
    @property
    def is_active(self) -> bool:
        now = datetime.utcnow()
        if self.revoked_at is not None:
            return False
        if self.valid_from is not None and now < self.valid_from:
            return False
        if self.expires_at is not None and now > self.expires_at:
            return False
        return True

    @field_validator('role_id', mode='before')
    @classmethod
    def validate_uuid(cls, val: Any) -> str:
        return str(val)

    @field_validator('id', 'revoked_by', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)


class ConnectorPermissionBulkUpdate(BaseModel):
    """Bulk update for connector-level department and role permissions."""
    departments: List[ConnectorDeptPermissionEntry] = []
    roles: List[ConnectorRolePermissionEntry] = []


class ConnectorPermissionGroupedOut(BaseModel):
    """Display connector permissions grouped by user, department, and role."""
    connector_id: str
    user_grants: List[dict]  # existing per-user rows
    department_grants: List[ConnectorDeptPermissionEntry]
    role_grants: List[ConnectorRolePermissionEntry]
    model_config = {"from_attributes": True}


# ─── Table-Level Permissions ─────────────────────────────────────────────────

class TablePermissionCreate(BaseModel):
    connector_id: str
    table_name: str
    applies_to_user_id: Optional[str] = None
    departments: List[DeptPermissionEntry] = []
    roles: List[RolePermissionEntry] = []
    can_read: bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False


class TablePermissionOut(BaseModel):
    id: str
    connector_id: str
    table_name: str
    applies_to_user_id: Optional[str] = None
    departments: List[DeptPermissionEntry] = []
    roles: List[RolePermissionEntry] = []
    can_read: bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False
    is_package_rule: Optional[bool] = False
    model_config = {"from_attributes": True}

    @field_validator('id', 'connector_id', 'applies_to_user_id', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)
