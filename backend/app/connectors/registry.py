from typing import Dict, Type
from app.connectors.base import BaseConnector
from app.connectors.postgres import PostgresConnector
from app.connectors.mysql import MySQLConnector
from app.connectors.mongodb import MongoDBConnector
from app.connectors.rest_api import RestAPIConnector
from app.connectors.sqlite import SQLiteConnector
from app.connectors.snowflake_conn import SnowflakeConnector
from app.connectors.mssql import MSSQLConnector
from app.connectors.elasticsearch import ElasticsearchConnector
from app.connectors.redis_conn import RedisConnector
from app.connectors.oracle import OracleConnector
from app.connectors.salesforce import SalesforceConnector
from app.models import ConnectorType

#  Plugin Registry 
# To add a new connector type:
# 1. Create a new file in app/connectors/
# 2. Implement BaseConnector
# 3. Add ConnectorType entry in models/__init__.py
# 4. Register here

CONNECTOR_REGISTRY: Dict[str, Type[BaseConnector]] = {
    ConnectorType.POSTGRES:       PostgresConnector,
    ConnectorType.MYSQL:          MySQLConnector,
    ConnectorType.SQLITE:         SQLiteConnector,
    ConnectorType.MSSQL:          MSSQLConnector,
    ConnectorType.ORACLE:         OracleConnector,
    ConnectorType.SNOWFLAKE:      SnowflakeConnector,
    ConnectorType.MONGODB:        MongoDBConnector,
    ConnectorType.ELASTICSEARCH:  ElasticsearchConnector,
    ConnectorType.REDIS:          RedisConnector,
    ConnectorType.SALESFORCE:     SalesforceConnector,
    ConnectorType.REST_API:       RestAPIConnector,
}


def get_connector(connector_type, config: dict) -> BaseConnector:
    """Get connector by type (enum or string)."""
    cls = CONNECTOR_REGISTRY.get(connector_type)
    if not cls:
        for k, v in CONNECTOR_REGISTRY.items():
            if str(k).lower() == str(connector_type).lower():
                cls = v
                break
    if not cls:
        available = [str(k) for k in CONNECTOR_REGISTRY.keys()]
        raise ValueError(f"No connector for type '{connector_type}'. Available: {available}")
    return cls(config)
