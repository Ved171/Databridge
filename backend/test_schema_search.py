import time
from app.services.schema_search import pick_cross_db_tables

# Mock database structure with multiple tables
mock_dbs = [
    {
        "id": "db1",
        "name": "Users DB",
        "type": "postgres",
        "tables": [
            {
                "name": "users",
                "schema": "public",
                "columns": [
                    {"name": "id", "type": "int"},
                    {"name": "email", "type": "varchar"},
                    {"name": "name", "type": "varchar"},
                ],
                "gotcha": "Some users may have null emails",
                "learned_filter": "is_active = true",
                "summary": "Main user accounts table"
            },
            {
                "name": "user_profiles",
                "schema": "public",
                "columns": [
                    {"name": "user_id", "type": "int"},
                    {"name": "bio", "type": "text"},
                ],
                "summary": "User profile information"
            },
            {
                "name": "permissions",
                "schema": "public",
                "columns": [
                    {"name": "id", "type": "int"},
                    {"name": "role", "type": "varchar"},
                ],
                "summary": "User roles and permissions"
            },
        ]
    },
    {
        "id": "db2",
        "name": "Analytics DB",
        "type": "mysql",
        "tables": [
            {
                "name": "events",
                "schema": "analytics",
                "columns": [
                    {"name": "event_id", "type": "bigint"},
                    {"name": "user_id", "type": "int"},
                    {"name": "event_type", "type": "varchar"},
                ],
                "summary": "User activity events"
            },
            {
                "name": "page_views",
                "schema": "analytics",
                "columns": [
                    {"name": "view_id", "type": "bigint"},
                    {"name": "user_id", "type": "int"},
                    {"name": "url", "type": "varchar"},
                ],
                "summary": "Page view tracking"
            },
        ]
    },
]

# Test 1: Fast query - should be < 5ms
start = time.time()
result1 = pick_cross_db_tables("Find user emails", mock_dbs)
elapsed1 = (time.time() - start) * 1000

print(f"Test 1 - 'Find user emails': {elapsed1:.2f}ms")
print(f"  Returned {len(result1)} databases with tables:")
for db in result1:
    print(f"    - {db['name']}: {len(db['tables'])} tables")

# Test 2: Another query
start = time.time()
result2 = pick_cross_db_tables("Show me event analytics and user names", mock_dbs)
elapsed2 = (time.time() - start) * 1000

print(f"\nTest 2 - 'Show me event analytics and user names': {elapsed2:.2f}ms")
print(f"  Returned {len(result2)} databases with tables:")
for db in result2:
    print(f"    - {db['name']}: {len(db['tables'])} tables")

# Verify performance
avg_time = (elapsed1 + elapsed2) / 2
if avg_time < 5:
    print(f"\n✓ Performance OK: Average {avg_time:.2f}ms (target < 5ms)")
else:
    print(f"\n⚠ Performance concern: Average {avg_time:.2f}ms (target < 5ms)")
