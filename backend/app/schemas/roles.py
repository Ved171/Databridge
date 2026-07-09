"""
app/schemas/roles.py
--------------------
Role-related Pydantic schemas.
"""
from pydantic import BaseModel, field_validator
from typing import Optional, List, Any


class RoleCreate(BaseModel):
    name: str
    color: str = '1E40AF'
    level: Optional[int] = 1
    parent_role_id: Optional[str] = None

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    level: Optional[int] = None
    parent_role_id: Optional[str] = None

class RoleOut(BaseModel):
    id: str
    name: str
    slug: str
    level: int
    color: str
    is_system: bool
    is_active: bool
    parent_role_id: Optional[str]
    member_count: int
    model_config = {"from_attributes": True}

    @field_validator('id', 'parent_role_id', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)

class RoleTreeNode(BaseModel):
    id: str
    name: str
    level: int
    member_count: int = 0
    color: str = '1E40AF'
    is_system: bool = False
    is_active: bool = True
    children: List['RoleTreeNode'] = []

    @field_validator('id', mode='before')
    @classmethod
    def validate_uuid(cls, val: Any) -> str:
        return str(val)
