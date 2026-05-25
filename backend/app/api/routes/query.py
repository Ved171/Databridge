"""
app/api/routes/query.py
───────────────────────
Single chat endpoint -- every question goes through the LangChain agent.
The agent decides which tools to use (single-db, cross-db, CRUD, etc.).
"""
import time
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User, QueryLog

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    message: str
    answer: str
    history: List[Dict[str, Any]] = []
    duration_ms: float

class QueryLogOut(BaseModel):
    id: str
    connector_id: Optional[str] = None
    natural_language: str
    generated_sql: Optional[str]
    status: str
    error_message: Optional[str]
    row_count: Optional[str]
    duration_ms: Optional[str]
    executed_at: Any
    model_config = {"from_attributes": True}


# ─── Chat Endpoint (DEPRECATED) ────────────────────────────────────────────────────────────
# The /chat and /chat/stream endpoints are deprecated.
# The client LLM should call DataBridge MCP tools directly instead.
# These endpoints remain for backwards compatibility but return a message.

@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    DEPRECATED: The agent service has been removed to move intelligence to the client.
    The client LLM should call DataBridge MCP tools directly.
    """
    raise HTTPException(
        status_code=410,
        detail="The /chat endpoint is deprecated. Please use MCP tools directly from your LLM."
    )


@router.get("/chat/stream")
async def chat_stream(
    message: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    DEPRECATED: The agent service has been removed to move intelligence to the client.
    """
    raise HTTPException(
        status_code=410,
        detail="The /chat/stream endpoint is deprecated. Please use MCP tools directly from your LLM."
    )


# ─── Logs ─────────────────────────────────────────────────────────────────────

@router.get("/logs", response_model=List[QueryLogOut])
async def get_query_logs(
    connector_id: str = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(QueryLog).order_by(QueryLog.executed_at.desc()).limit(limit)

    if not current_user.is_superadmin:
        query = query.where(QueryLog.user_id == current_user.id)
    if connector_id:
        query = query.where(QueryLog.connector_id == connector_id)

    result = await db.execute(query)
    return result.scalars().all()
