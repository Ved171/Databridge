"""
app/schemas/departments.py
--------------------------
Department-related Pydantic schemas.
"""
from pydantic import BaseModel, field_validator
from typing import Optional, Any


class DepartmentCreate(BaseModel):
    name: str
    color: str = '1E40AF'
    default_role_id: Optional[str] = None
    parent_department_id: Optional[str] = None

class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None
    default_role_id: Optional[str] = None

class DepartmentOut(BaseModel):
    id: str
    name: str
    slug: str
    color: str
    is_active: bool
    is_system: bool = False
    default_role_id: Optional[str]
    parent_department_id: Optional[str]
    member_count: int
    model_config = {"from_attributes": True}

    @field_validator('id', 'default_role_id', 'parent_department_id', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)
