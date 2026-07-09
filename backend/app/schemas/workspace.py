"""
app/schemas/workspace.py
------------------------
Workspace-related Pydantic schemas.
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.enums import UserRole


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
