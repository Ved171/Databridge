"""
app/schemas/query.py
--------------------
Query-related Pydantic schemas.
"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


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
