"""
app/tools/nosql_rls.py

Row-Level Security injection for NoSQL connectors:
   MongoDB:        Prepends $match stage to aggregation pipelines
   Elasticsearch:  Wraps queries in bool.filter clauses
   Redis:          Restricts key patterns to allowed prefixes
   Salesforce:     Injects WHERE clauses into SOQL queries

Each engine reads from `policy.filter_expr_nosql` (JSON), resolves
user variables ({user.id}, {user.email}, {user.name}), and mutates
the query JSON before it reaches the connector driver.
"""
from __future__ import annotations

import copy
import json
import logging
import re
import fnmatch
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# 
# Shared helpers
# 

def _resolve_user_vars(value: str, user_ctx: Dict) -> str:
    """Replace {user.id}, {user.email}, {user.name} in a string value."""
    if not isinstance(value, str):
        return value
    value = value.replace("{user.id}", str(user_ctx.get("id", "")))
    value = value.replace("{user.email}", str(user_ctx.get("email", "")))
    value = value.replace("{user.name}", str(user_ctx.get("name", "")))
    # Legacy placeholders from sql_helpers
    value = value.replace("{user_id}", str(user_ctx.get("id", "")))
    value = value.replace("{user_email}", str(user_ctx.get("email", "")))
    value = value.replace("{user_name}", str(user_ctx.get("name", "")))
    return value


def _resolve_nosql_filter(filter_obj: dict, user_ctx: Dict) -> dict:
    """Deep-resolve user variables in a NoSQL filter JSON object."""
    resolved = {}
    for key, val in filter_obj.items():
        if isinstance(val, str):
            resolved[key] = _resolve_user_vars(val, user_ctx)
        elif isinstance(val, dict):
            resolved[key] = _resolve_nosql_filter(val, user_ctx)
        elif isinstance(val, list):
            resolved[key] = [
                _resolve_nosql_filter(item, user_ctx) if isinstance(item, dict)
                else _resolve_user_vars(item, user_ctx) if isinstance(item, str)
                else item
                for item in val
            ]
        else:
            resolved[key] = val
    return resolved


def _get_matching_policies(policies: list, table_name: str, user_ctx: Dict) -> List[dict]:
    """
    Filter policies that match the given table/collection/index name,
    and resolve their filter_expr_nosql with user variables.
    Returns a list of resolved filter dicts.
    """
    resolved_filters = []
    for policy in policies:
        policy_table = getattr(policy, "table_name", None) or ""
        nosql_filter = getattr(policy, "filter_expr_nosql", None)

        if not nosql_filter:
            continue

        # Match by exact table name or wildcard "*"
        if policy_table != table_name and policy_table != "*":
            continue

        resolved = _resolve_nosql_filter(nosql_filter, user_ctx)
        resolved_filters.append(resolved)

    return resolved_filters


def _parse_filter_condition(filter_obj: dict) -> tuple[str, str, Any]:
    if "field" in filter_obj and "op" in filter_obj:
        return filter_obj["field"], filter_obj["op"].lower(), filter_obj.get("value")
    for k, v in filter_obj.items():
        return k, "eq", v
    return "", "", None


def _build_mongo_match(filter_obj: dict) -> dict:
    """
    Convert a NoSQL filter object into a MongoDB $match expression.

    Supported formats:
      {"field": "org_id", "op": "eq", "value": "abc"}
         {"org_id": "abc"}
      {"field": "status", "op": "in", "value": ["active", "pending"]}
         {"status": {"$in": ["active", "pending"]}}
      {"field": "age", "op": "gt", "value": 18}
         {"age": {"$gt": 18}}
      {"org_id": "abc"}   (raw MongoDB filter -- passed through)
         {"org_id": "abc"}
    """
    if "field" in filter_obj and "op" in filter_obj:
        field = filter_obj["field"]
        op = filter_obj["op"].lower()
        value = filter_obj.get("value")

        op_map = {
            "eq": lambda v: v,
            "ne": lambda v: {"$ne": v},
            "gt": lambda v: {"$gt": v},
            "gte": lambda v: {"$gte": v},
            "lt": lambda v: {"$lt": v},
            "lte": lambda v: {"$lte": v},
            "in": lambda v: {"$in": v if isinstance(v, list) else [v]},
            "nin": lambda v: {"$nin": v if isinstance(v, list) else [v]},
            "exists": lambda v: {"$exists": v},
            "regex": lambda v: {"$regex": v},
        }

        converter = op_map.get(op)
        if converter:
            return {field: converter(value)}
        else:
            logger.warning("Unknown NoSQL RLS operator '%s', treating as eq", op)
            return {field: value}
    else:
        # Raw MongoDB filter object -- pass through directly
        return filter_obj


# 
# MongoDB RLS
# 

def apply_rls_mongodb(query_json: str, policies: list, user_ctx: Dict) -> str:
    """
    Inject $match stages into MongoDB aggregation pipelines.
    Supports write operations (insertOne, updateOne, deleteOne) as well.

    Prepends a $match stage at the beginning of the pipeline so that
    documents are filtered BEFORE any $group, $sort, or $project stages.
    Multiple policies for the same collection are combined with $and.
    """
    try:
        query = json.loads(query_json)
    except json.JSONDecodeError:
        logger.warning("MongoDB RLS: Failed to parse query JSON")
        return query_json

    collection = query.get("collection", "")
    operation = query.get("operation")

    filters = _get_matching_policies(policies, collection, user_ctx)
    if not filters:
        return query_json

    if operation:
        if operation == "insertOne":
            doc = query.get("document", {})
            for f in filters:
                field, op, val = _parse_filter_condition(f)
                if op == "eq":
                    if field not in doc:
                        doc[field] = val
                    elif doc[field] != val:
                        return json.dumps({"error": f"RLS: Write denied. Field '{field}' must be '{val}'"})
                elif op == "in":
                    val_list = val if isinstance(val, list) else [val]
                    if field not in doc:
                        if len(val_list) == 1:
                            doc[field] = val_list[0]
                        else:
                            return json.dumps({"error": f"RLS: Write denied. Missing required field '{field}' (must be one of {val_list})"})
                    elif doc[field] not in val_list:
                        return json.dumps({"error": f"RLS: Write denied. Field '{field}' must be one of {val_list}"})
            query["document"] = doc
            return json.dumps(query)

        elif operation in ("updateOne", "deleteOne"):
            filter_obj = query.get("filter", {})
            match_conditions = [_build_mongo_match(f) for f in filters]
            if len(match_conditions) == 1:
                filter_obj.update(match_conditions[0])
            else:
                if "$and" not in filter_obj:
                    filter_obj["$and"] = []
                filter_obj["$and"].extend(match_conditions)
            query["filter"] = filter_obj

            if operation == "updateOne":
                update_payload = query.get("update", {})
                for op_key, fields_dict in update_payload.items():
                    if op_key in ("$set", "$unset"):
                        for f in filters:
                            field, op, val = _parse_filter_condition(f)
                            if field in fields_dict:
                                if op_key == "$unset":
                                    return json.dumps({"error": f"RLS: Write denied. Cannot unset RLS field '{field}'"})
                                if op == "eq" and fields_dict[field] != val:
                                    return json.dumps({"error": f"RLS: Write denied. Field '{field}' must be '{val}'"})
                                elif op == "in" and fields_dict[field] not in (val if isinstance(val, list) else [val]):
                                    return json.dumps({"error": f"RLS: Write denied. Field '{field}' must be one of {val}"})
            return json.dumps(query)

    # Read operation (pipeline)
    pipeline = query.get("pipeline", [])
    match_conditions = [_build_mongo_match(f) for f in filters]

    if len(match_conditions) == 1:
        match_stage = {"$match": match_conditions[0]}
    else:
        match_stage = {"$match": {"$and": match_conditions}}

    query["pipeline"] = [match_stage] + pipeline
    return json.dumps(query)


# 
# Elasticsearch RLS
# 

def _build_es_filter(filter_obj: dict) -> dict:
    """
    Convert a NoSQL filter object into an Elasticsearch filter clause.

    Supported formats:
      {"field": "tenant_id", "op": "eq", "value": "abc"}
         {"term": {"tenant_id": "abc"}}
      {"field": "status", "op": "in", "value": ["active", "pending"]}
         {"terms": {"status": ["active", "pending"]}}
      {"field": "age", "op": "gt", "value": 18}
         {"range": {"age": {"gt": 18}}}
      {"term": {"tenant_id": "abc"}}   (raw ES filter -- passed through)
         {"term": {"tenant_id": "abc"}}
    """
    if "field" in filter_obj and "op" in filter_obj:
        field = filter_obj["field"]
        op = filter_obj["op"].lower()
        value = filter_obj.get("value")

        if op == "eq":
            return {"term": {field: value}}
        elif op == "ne":
            return {"bool": {"must_not": [{"term": {field: value}}]}}
        elif op in ("gt", "gte", "lt", "lte"):
            return {"range": {field: {op: value}}}
        elif op == "in":
            return {"terms": {field: value if isinstance(value, list) else [value]}}
        elif op == "exists":
            return {"exists": {"field": field}}
        elif op == "regex":
            return {"regexp": {field: value}}
        else:
            logger.warning("Unknown ES RLS operator '%s', treating as term", op)
            return {"term": {field: value}}
    else:
        # Raw ES filter -- pass through
        return filter_obj


def apply_rls_elasticsearch(query_json: str, policies: list, user_ctx: Dict) -> str:
    """
    Wrap Elasticsearch queries in bool.filter clauses.
    Supports write operations (index) as well.

    If the query already uses a bool query, the RLS filters are merged
    into the existing filter array. Otherwise, the original query is
    wrapped inside a bool.must and the RLS filter is added as bool.filter.
    """
    try:
        query = json.loads(query_json)
    except json.JSONDecodeError:
        logger.warning("ES RLS: Failed to parse query JSON")
        return query_json

    index = query.get("index", "")
    operation = query.get("operation")
    filters = _get_matching_policies(policies, index, user_ctx)
    if not filters:
        return query_json

    if operation == "index":
        doc = query.get("document", {})
        for f in filters:
            field, op, val = _parse_filter_condition(f)
            if op == "eq":
                if field not in doc:
                    doc[field] = val
                elif doc[field] != val:
                    return json.dumps({"error": f"RLS: Write denied. Field '{field}' must be '{val}'"})
            elif op == "in":
                val_list = val if isinstance(val, list) else [val]
                if field not in doc:
                    if len(val_list) == 1:
                        doc[field] = val_list[0]
                    else:
                        return json.dumps({"error": f"RLS: Write denied. Missing required field '{field}' (must be one of {val_list})"})
                elif doc[field] not in val_list:
                    return json.dumps({"error": f"RLS: Write denied. Field '{field}' must be one of {val_list}"})
        query["document"] = doc
        return json.dumps(query)

    es_filters = [_build_es_filter(f) for f in filters]

    # Get the existing query body
    existing_query = query.get("query", {"match_all": {}})

    if isinstance(existing_query, dict) and "bool" in existing_query:
        # Merge into existing bool query
        bool_query = existing_query["bool"]
        if "filter" not in bool_query:
            bool_query["filter"] = []
        elif not isinstance(bool_query["filter"], list):
            bool_query["filter"] = [bool_query["filter"]]
        bool_query["filter"].extend(es_filters)
    else:
        # Wrap the existing query in a bool
        query["query"] = {
            "bool": {
                "must": [existing_query],
                "filter": es_filters,
            }
        }

    return json.dumps(query)


# 
# Redis RLS -- Key-Prefix Restriction
# 

def apply_rls_redis(query_json: str, policies: list, user_ctx: Dict) -> str:
    """
    Restrict Redis key access to allowed key-prefix patterns.

    Policy filter_expr_nosql format:
      {"key_pattern": "org:{user.id}:*"}

    For SCAN commands: narrows the scan pattern to the intersection
    of the requested and allowed patterns.
    For GET/HGETALL/DEL/SET: validates the target key against allowed patterns.
    If no policy matches or the key is outside allowed patterns, returns an error.
    """
    try:
        query = json.loads(query_json)
    except json.JSONDecodeError:
        logger.warning("Redis RLS: Failed to parse query JSON")
        return query_json

    # Redis doesn't have collections/tables -- match on key prefix table_name
    # The table_name in the RLS policy corresponds to the Redis key prefix
    cmd = query.get("command", "").upper()

    # Collect all allowed key patterns from matching policies
    allowed_patterns = []
    for policy in policies:
        nosql_filter = getattr(policy, "filter_expr_nosql", None)
        if not nosql_filter:
            continue
        resolved = _resolve_nosql_filter(nosql_filter, user_ctx)
        pattern = resolved.get("key_pattern", "")
        if pattern:
            allowed_patterns.append(pattern)

    if not allowed_patterns:
        return query_json

    if cmd == "SCAN":
        requested_pattern = query.get("pattern", "*")
        # Restrict: use the most specific allowed pattern
        # If the requested pattern is broader than allowed, narrow it
        restricted = _restrict_scan_pattern(requested_pattern, allowed_patterns)
        query["pattern"] = restricted
        return json.dumps(query)

    elif cmd in ("GET", "HGETALL", "SET", "DEL"):
        args = query.get("args", [])
        if args:
            target_key = args[0]
            if not _key_matches_any_pattern(target_key, allowed_patterns):
                return json.dumps({
                    "error": f"RLS: Access denied. Key '{target_key}' is outside your allowed scope.",
                    "allowed_patterns": allowed_patterns,
                })
        return json.dumps(query)

    else:
        # For other commands, pass through but log a warning
        logger.warning("Redis RLS: Unhandled command '%s', passing through", cmd)
        return json.dumps(query)


def _restrict_scan_pattern(requested: str, allowed: List[str]) -> str:
    """
    Restrict a SCAN pattern to the narrowest allowed pattern.
    If the requested pattern is already within an allowed pattern, keep it.
    Otherwise, use the first allowed pattern.
    """
    for allowed_pat in allowed:
        # If the requested pattern is a sub-pattern of the allowed one
        if requested.startswith(allowed_pat.rstrip("*")):
            return requested
    # Default to the first allowed pattern
    return allowed[0]


def _key_matches_any_pattern(key: str, patterns: List[str]) -> bool:
    """Check if a key matches any of the allowed glob patterns."""
    for pattern in patterns:
        if fnmatch.fnmatch(key, pattern):
            return True
    return False


# 
# Salesforce RLS -- SOQL WHERE injection
# 

def apply_rls_salesforce(query_str: str, policies: list, user_ctx: Dict) -> str:
    """
    Inject WHERE clauses into Salesforce SOQL queries.

    For SOQL strings (SELECT ...): injects SQL-style WHERE fragments
    using the policy's filter_expr field (same as SQL RLS).

    For JSON CRUD operations ({...}): validates the target object
    against RLS policies. For inserts, injects required field values.
    """
    stripped = query_str.strip()

    if stripped.startswith("{"):
        # JSON CRUD operation -- extract the object name and validate
        try:
            obj = json.loads(stripped)
            object_name = obj.get("object", "")
            operation = obj.get("operation", "").lower()

            for policy in policies:
                policy_table = getattr(policy, "table_name", "") or ""
                if policy_table != object_name and policy_table != "*":
                    continue

                # For SOQL CRUD, use filter_expr_nosql if available
                nosql_filter = getattr(policy, "filter_expr_nosql", None)
                if nosql_filter:
                    resolved = _resolve_nosql_filter(nosql_filter, user_ctx)
                    field, op, value = _parse_filter_condition(resolved)

                    if operation == "insert":
                        # Auto-inject the RLS field into the data
                        data = obj.get("data", {})
                        if field:
                            if op == "eq":
                                if field not in data:
                                    data[field] = value
                                elif data[field] != value:
                                    return json.dumps({"error": f"RLS: Write denied. Field '{field}' must be '{value}'"})
                            elif op == "in":
                                val_list = value if isinstance(value, list) else [value]
                                if field not in data:
                                    if len(val_list) == 1:
                                        data[field] = val_list[0]
                                    else:
                                        return json.dumps({"error": f"RLS: Write denied. Missing required field '{field}' (must be one of {val_list})"})
                                elif data[field] not in val_list:
                                    return json.dumps({"error": f"RLS: Write denied. Field '{field}' must be one of {val_list}"})
                        obj["data"] = data
                    elif operation == "update":
                        data = obj.get("data", {})
                        if field:
                            if op == "eq" and field in data and data[field] != value:
                                return json.dumps({"error": f"RLS: Write denied. Field '{field}' must be '{value}'"})
                            elif op == "in" and field in data and data[field] not in (value if isinstance(value, list) else [value]):
                                return json.dumps({"error": f"RLS: Write denied. Field '{field}' must be one of {value}"})

            return json.dumps(obj)
        except json.JSONDecodeError:
            return query_str

    # SOQL SELECT query -- inject WHERE conditions
    rls_conditions = []
    for policy in policies:
        # For Salesforce, we can use the SQL filter_expr directly on SOQL
        sql_filter = getattr(policy, "filter_expr", None)
        if sql_filter:
            resolved = _resolve_user_vars(sql_filter, user_ctx)
            rls_conditions.append(f"({resolved})")
            continue

        # Also support filter_expr_nosql for Salesforce
        nosql_filter = getattr(policy, "filter_expr_nosql", None)
        if nosql_filter:
            resolved = _resolve_nosql_filter(nosql_filter, user_ctx)
            field = resolved.get("field", "")
            value = resolved.get("value", "")
            op = resolved.get("op", "eq").lower()

            if op == "eq":
                rls_conditions.append(f"({field} = '{value}')")
            elif op == "ne":
                rls_conditions.append(f"({field} != '{value}')")
            elif op == "in":
                vals = value if isinstance(value, list) else [value]
                in_str = ",".join(f"'{v}'" for v in vals)
                rls_conditions.append(f"({field} IN ({in_str}))")

    if not rls_conditions:
        return query_str

    combined_rls = " AND ".join(rls_conditions)

    # Inject into SOQL (similar logic to SQL WHERE injection)
    where_pattern = re.compile(r"\bWHERE\b", re.IGNORECASE)
    if where_pattern.search(query_str):
        new_query = where_pattern.sub(
            f"WHERE ({combined_rls}) AND ",
            query_str,
            count=1,
        )
        return new_query
    else:
        # Insert before ORDER BY, GROUP BY, LIMIT
        insert_pattern = re.compile(r"\b(ORDER BY|GROUP BY|LIMIT)\b", re.IGNORECASE)
        match = insert_pattern.search(query_str)
        if match:
            pos = match.start()
            return query_str[:pos] + f" WHERE {combined_rls} " + query_str[pos:]
        else:
            return query_str + f" WHERE {combined_rls}"


# 
# Router -- dispatches to the correct engine
# 

def apply_rls_nosql(
    query_json: str,
    connector_type: str,
    policies: list,
    user_ctx: Dict,
) -> str:
    """
    Apply NoSQL RLS to a query based on connector type.

    Routes to the appropriate engine: MongoDB, Elasticsearch, Redis,
    or Salesforce. Returns the modified query JSON string.
    """
    ct = connector_type.lower()

    if ct == "mongodb":
        return apply_rls_mongodb(query_json, policies, user_ctx)
    elif ct == "elasticsearch":
        return apply_rls_elasticsearch(query_json, policies, user_ctx)
    elif ct == "redis":
        return apply_rls_redis(query_json, policies, user_ctx)
    elif ct == "salesforce":
        return apply_rls_salesforce(query_json, policies, user_ctx)
    else:
        logger.warning(
            "NoSQL RLS: No engine for connector type '%s', skipping", ct
        )
        return query_json
