from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import pyarrow as pa


@dataclass
class ConnectorCapabilities:
    supports_projection_pushdown: bool = False
    supports_predicate_pushdown: bool = False
    supports_groupby_pushdown: bool = False
    supports_window_functions: bool = False
    supports_cte: bool = False
    supports_limit_pushdown: bool = False
    supports_orderby_pushdown: bool = False
    supports_arrow_streaming: bool = False


CONNECTOR_CAPABILITIES: Dict[str, ConnectorCapabilities] = {
    "snowflake": ConnectorCapabilities(
        supports_projection_pushdown=True,
        supports_predicate_pushdown=True,
        supports_groupby_pushdown=True,
        supports_window_functions=True,
        supports_cte=True,
        supports_limit_pushdown=True,
        supports_orderby_pushdown=True,
        supports_arrow_streaming=True,
    ),
    "postgres": ConnectorCapabilities(
        supports_projection_pushdown=True,
        supports_predicate_pushdown=True,
        supports_groupby_pushdown=True,
        supports_cte=True,
        supports_limit_pushdown=True,
        supports_orderby_pushdown=True,
        supports_arrow_streaming=True,
    ),
    "postgresql": ConnectorCapabilities(
        supports_projection_pushdown=True,
        supports_predicate_pushdown=True,
        supports_groupby_pushdown=True,
        supports_cte=True,
        supports_limit_pushdown=True,
        supports_orderby_pushdown=True,
        supports_arrow_streaming=True,
    ),
    "redshift": ConnectorCapabilities(
        supports_projection_pushdown=True,
        supports_predicate_pushdown=True,
        supports_groupby_pushdown=True,
        supports_cte=True,
        supports_limit_pushdown=True,
        supports_orderby_pushdown=True,
        supports_arrow_streaming=True,
    ),
    "mssql": ConnectorCapabilities(
        supports_projection_pushdown=True,
        supports_predicate_pushdown=True,
        supports_groupby_pushdown=True,
        supports_cte=True,
    ),
    "mysql": ConnectorCapabilities(
        supports_projection_pushdown=True,
        supports_predicate_pushdown=True,
        supports_groupby_pushdown=True,
    ),
    "mariadb": ConnectorCapabilities(
        supports_projection_pushdown=True,
        supports_predicate_pushdown=True,
        supports_groupby_pushdown=True,
    ),
    "sqlite": ConnectorCapabilities(
        supports_projection_pushdown=True,
        supports_predicate_pushdown=True,
        supports_groupby_pushdown=True,
    ),
}


def get_connector_capabilities(db_type: str) -> ConnectorCapabilities:
    return CONNECTOR_CAPABILITIES.get(db_type.lower(), ConnectorCapabilities())


@dataclass
class ColumnInfo:
    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False


@dataclass
class TableInfo:
    name: str
    columns: List[ColumnInfo]
    row_count: Optional[int] = None
    schema: Optional[str] = None


@dataclass
class QueryResult:
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    duration_ms: float
    pa_table: Optional[pa.Table] = None


class BaseConnector(ABC):
    """
    Every connector adapter implements this interface.
    Adding a new DB type = create a new class, register it in CONNECTOR_REGISTRY.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    async def test_connection(self) -> bool:
        """Verify the connection works. Raises on failure."""
        ...

    @abstractmethod
    async def get_schema(self) -> List[TableInfo]:
        """Return all tables and their columns."""
        ...

    @abstractmethod
    async def execute_query(self, sql: str) -> QueryResult:
        """Execute a SQL (or translated) query and return results."""
        ...

    def get_schema_prompt(self, tables: List[TableInfo]) -> str:
        """
        Build a schema description for LLM injection.
        Override per connector if the syntax differs.
        """
        lines = []
        for table in tables:
            cols = ", ".join(
                f"{c.name} {c.type}{'(PK)' if c.primary_key else ''}"
                for c in table.columns
            )
            lines.append(f"Table: {table.name} ({cols})")
        return "\n".join(lines)
