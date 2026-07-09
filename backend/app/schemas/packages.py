"""
app/schemas/packages.py
-----------------------
Access Package related Pydantic schemas.
"""
from pydantic import BaseModel, field_validator
from typing import Optional, List, Any
from datetime import datetime


class PackageConnectorRuleIn(BaseModel):
    connector_id: str
    is_deny:    bool = False
    can_read:   bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False
    model_config = {"from_attributes": True}

class PackageTableRuleIn(BaseModel):
    connector_id:     str
    table_name:       str
    is_deny:          bool = False
    can_read:         bool = True
    can_create:       bool = False
    can_update:       bool = False
    can_delete:       bool = False
    model_config = {"from_attributes": True}

class PackageRLSFilterIn(BaseModel):
    connector_id:     str
    table_name:       str
    filter_expression: str
    model_config = {"from_attributes": True}

class PackageCreate(BaseModel):
    name:              str
    description:       Optional[str] = None
    color:             str = '1E40AF'
    connector_rules:   List[PackageConnectorRuleIn] = []
    table_rules:       List[PackageTableRuleIn] = []
    rls_filters:       List[PackageRLSFilterIn] = []

class DeptRoleAssignmentIn(BaseModel):
    """Assigns a package to a specific role within a department."""
    department_id: str
    role_id: str

class PackageAssignIn(BaseModel):
    department_ids: List[str] = []
    role_ids:       List[str] = []
    dept_role_assignments: List[DeptRoleAssignmentIn] = []  # combined dept+role
    valid_from:     Optional[datetime] = None
    expires_at:     Optional[datetime] = None

class PackageDeptAssignmentOut(BaseModel):
    id: str
    department_id: str
    role_id: Optional[str] = None
    valid_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    assigned_by: str
    assigned_at: datetime
    model_config = {"from_attributes": True}

    @field_validator('id', 'department_id', 'role_id', 'revoked_by', 'assigned_by', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)

class PackageRoleAssignmentOut(BaseModel):
    id: str
    role_id: str
    valid_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    assigned_by: str
    assigned_at: datetime
    model_config = {"from_attributes": True}

    @field_validator('id', 'role_id', 'revoked_by', 'assigned_by', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)

class PackageOut(BaseModel):
    id:              str
    name:            str
    slug:            str
    description:     Optional[str]
    color:           str
    is_active:       bool
    connector_rules: List[PackageConnectorRuleIn]
    table_rules:     List[PackageTableRuleIn]
    rls_filters:     List[PackageRLSFilterIn]
    dept_assignments: List[PackageDeptAssignmentOut]
    role_assignments: List[PackageRoleAssignmentOut]
    created_at:      datetime
    model_config = {"from_attributes": True}

    @field_validator('id', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)
