"""
app/models/enums.py
-------------------
Shared enums used across all models.
"""
import enum


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    WORKSPACE_ADMIN = "workspace_admin"
    MEMBER = "member"
    VIEWER = "viewer"


class ConnectorType(str, enum.Enum):
    # Relational SQL
    POSTGRES      = "postgres"
    MYSQL         = "mysql"
    SQLITE        = "sqlite"
    MSSQL         = "mssql"
    ORACLE        = "oracle"
    SNOWFLAKE     = "snowflake"
    REDSHIFT      = "redshift"
    BIGQUERY      = "bigquery"
    # NoSQL / Document
    MONGODB       = "mongodb"
    ELASTICSEARCH = "elasticsearch"
    REDIS         = "redis"
    DYNAMODB      = "dynamodb"
    # SaaS / API
    SALESFORCE    = "salesforce"
    REST_API      = "rest_api"
    AIRTABLE      = "airtable"


class PermissionLevel(str, enum.Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
