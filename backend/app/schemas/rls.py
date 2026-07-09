"""
app/schemas/rls.py
------------------
RLS-related Pydantic schemas.
"""
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.enums import UserRole


class RLSPolicyCreate(BaseModel):
    name: str
    table_name: str
    filter_expr: Optional[str] = None          # SQL WHERE fragment (for SQL connectors)
    filter_expr_nosql: Optional[Dict] = None   # JSON filter (for NoSQL connectors)
    applies_to_user_id: Optional[str] = None
    applies_to_role: Optional[UserRole] = None

class RLSPolicyUpdate(BaseModel):
    name: Optional[str] = None
    table_name: Optional[str] = None
    filter_expr: Optional[str] = None
    filter_expr_nosql: Optional[Dict] = None
    applies_to_user_id: Optional[str] = None
    applies_to_role: Optional[UserRole] = None

class RLSPolicyOut(BaseModel):
    id: str
    connector_id: str
    name: str
    table_name: str
    filter_expr: Optional[str] = None
    filter_expr_nosql: Optional[Dict] = None
    applies_to_user_id: Optional[str]
    applies_to_role: Optional[UserRole]
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class RLSFilterCreate(BaseModel):
    connector_id:       str
    table_name:         str
    filter_expression:  str
    applies_to_role_id: Optional[str] = None
    applies_to_dept_id: Optional[str] = None
    applies_to_user_id: Optional[str] = None

    @field_validator('filter_expression')
    @classmethod
    def must_contain_placeholder(cls, v: str) -> str:
        import re
        if not re.search(r'\{[\w.]+\}', v):
            raise ValueError("filter_expression must contain at least one {placeholder}.")
        return v

    @model_validator(mode='after')
    def must_have_target(self) -> 'RLSFilterCreate':
        if not any([self.applies_to_role_id, self.applies_to_dept_id, self.applies_to_user_id]):
            raise ValueError("At least one of applies_to_role_id, applies_to_dept_id, applies_to_user_id must be set.")
        return self


class RLSFilterOut(BaseModel):
    id:                 str
    connector_id:       str
    table_name:         str
    filter_expression:  str
    applies_to_role_id: Optional[str] = None
    applies_to_dept_id: Optional[str] = None
    applies_to_user_id: Optional[str] = None
    is_active:          bool
    created_at:         datetime
    is_package_rule:    Optional[bool] = False
    model_config = {"from_attributes": True}

    @field_validator('id', 'applies_to_role_id', 'applies_to_dept_id', 'applies_to_user_id', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)


class RLSContextOut(BaseModel):
    """What the debug endpoint returns — shows resolved placeholder values."""
    user_id:                  str
    user_email:               str
    user_employee_code:       Optional[str] = None
    managed_codes:            List[str]
    managed_user_ids:         List[str]
    managed_count:            int
    is_manager:               bool
