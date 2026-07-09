"""
app/schemas/notifications.py
-----------------------------
Notification Pydantic schemas.
"""
from pydantic import BaseModel, field_validator
from typing import Optional, Any
from datetime import datetime


class NotificationOut(BaseModel):
    id: str
    user_id: str
    title: str
    message: str
    is_read: bool
    created_at: datetime
    model_config = {"from_attributes": True}

    @field_validator('id', 'user_id', mode='before')
    @classmethod
    def validate_uuids(cls, val: Any) -> Optional[str]:
        if val is None:
            return None
        return str(val)
