from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import check_connector_permission, get_current_user
from app.models import Connector, User
from app.tools.mcp_metadata import MCP_RESOURCE_URIS, MCP_TOOL_NAMES

router = APIRouter()


def _connector_type(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


@router.get("/summary")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Connector))
    all_connectors = result.scalars().all()

    access_cache: dict = {}
    accessible_active_connectors = []
    accessible_inactive_connectors = []
    operation_counts = {"read": 0, "create": 0, "update": 0, "delete": 0}
    writable_connector_count = 0
    accessible_serialized = []

    for connector in all_connectors:
        # Check read permission
        can_read = await check_connector_permission(
            connector.id,
            "read",
            current_user,
            db,
            _cache=access_cache,
        )
        if can_read:
            can_create = await check_connector_permission(connector.id, "create", current_user, db, _cache=access_cache)
            can_update = await check_connector_permission(connector.id, "update", current_user, db, _cache=access_cache)
            can_delete = await check_connector_permission(connector.id, "delete", current_user, db, _cache=access_cache)
            
            if can_create:
                operation_counts["create"] += 1
            if can_update:
                operation_counts["update"] += 1
            if can_delete:
                operation_counts["delete"] += 1
            if can_create or can_update or can_delete:
                writable_connector_count += 1
                
            operation_counts["read"] += 1

            if connector.is_active:
                accessible_active_connectors.append(connector)
                accessible_serialized.append(
                    {
                        "id": connector.id,
                        "name": connector.name,
                        "type": _connector_type(connector.type),
                        "is_active": connector.is_active,
                        "schema_cached_at": connector.schema_cached_at,
                        "can_read": True,
                        "can_create": can_create,
                        "can_update": can_update,
                        "can_delete": can_delete,
                    }
                )
            else:
                accessible_inactive_connectors.append(connector)

    cached_connectors = [c for c in accessible_active_connectors if c.schema_cached_at]
    ready_connectors = [c for c in accessible_active_connectors if c.schema_cached_at]
    needs_schema = [c for c in accessible_active_connectors if not c.schema_cached_at]
    inactive_connectors = accessible_inactive_connectors

    type_counts: dict[str, int] = {}
    for connector in accessible_active_connectors:
        connector_type = _connector_type(connector.type)
        type_counts[connector_type] = type_counts.get(connector_type, 0) + 1

    total_active = len(accessible_active_connectors)
    read_access_count = operation_counts["read"]

    return {
        "mcp": {
            "tool_count": len(MCP_TOOL_NAMES),
            "resource_count": len(MCP_RESOURCE_URIS),
            "tools": MCP_TOOL_NAMES,
            "resources": MCP_RESOURCE_URIS,
        },
        "connectors": {
            "total": len(accessible_active_connectors) + len(accessible_inactive_connectors),
            "active": total_active,
            "inactive": len(inactive_connectors),
            "schema_cached": len(cached_connectors),
            "ready": len(ready_connectors),
            "needs_schema": len(needs_schema),
            "schema_readiness_pct": round((len(cached_connectors) / total_active) * 100) if total_active else None,
            "type_distribution": [
                {
                    "type": connector_type,
                    "count": count,
                    "pct": round((count / total_active) * 100) if total_active else 0,
                }
                for connector_type, count in sorted(type_counts.items(), key=lambda item: item[1], reverse=True)
            ],
        },
        "access": {
            "read": read_access_count,
            "create": operation_counts["create"],
            "update": operation_counts["update"],
            "delete": operation_counts["delete"],
            "write": writable_connector_count,
            "coverage_pct": round((read_access_count / total_active) * 100) if total_active else None,
            "accessible_connectors": accessible_serialized,
        },
    }
