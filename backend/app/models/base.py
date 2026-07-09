"""
app/models/base.py
------------------
Shared base utilities for all models.
"""
import uuid

from app.core.database import Base


def gen_uuid():
    return str(uuid.uuid4())
