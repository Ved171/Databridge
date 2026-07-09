"""
app/schemas/user.py
-------------------
User-related Pydantic schemas.
"""
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, Any
from datetime import datetime
from app.models.enums import UserRole


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

class CreateUserRequest(BaseModel):
    name: str
    email: str
    department_id: str
    role_id: str

class AcceptInviteRequest(BaseModel):
    token: str
    password: str
    confirm_password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

class UserOut(BaseModel):
    id: str
    email: str
    name: str
    is_active: bool
    is_superadmin: bool
    force_password_change: bool
    department_id: Optional[str] = None
    role_id: Optional[str] = None
    role: str = "member"
    created_at: datetime
    model_config = {"from_attributes": True}

    @field_validator('role', mode='before')
    @classmethod
    def validate_role(cls, role: Any) -> str:
        if not role:
            return "member"
        if isinstance(role, str):
            return role
        try:
            return role.slug
        except Exception:
            return "member"

    @field_validator('role_id', 'department_id', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)
