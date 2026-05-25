import json
from pathlib import Path
from app.services.atlas_builder import get_atlas_builder, transform_schema_to_atlas_tables

BASE = Path(__file__).resolve().parent.parent / 'app'
SCHEMA_FILE = BASE / 'databridge_schema_summary_min.json'

with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)

dbs = data.get('dbs', {})

builder = get_atlas_builder()

for db_key, db_val in dbs.items():
    connector_id = db_key
    connector_type = db_val.get('type', '')
    db_name = db_val.get('name', db_key)  # Use 'name' field if available, otherwise use key
    tbls = db_val.get('tbls', {})
    tables = []
    for tbl_key, tbl_val in tbls.items():
        # split schema and table name if dotted
        if '.' in tbl_key:
            schema, name = tbl_key.split('.', 1)
        else:
            schema = ''
            name = tbl_key
        cols = []
        raw_cols = tbl_val.get('cols', [])
        for c in raw_cols:
            if isinstance(c, str):
                parts = c.split(':')
                col_name = parts[0]
                col_type = parts[1] if len(parts) > 1 else ''
                cols.append({'name': col_name, 'type': col_type})
            elif isinstance(c, dict):
                cols.append(c)
            else:
                cols.append({'name': str(c), 'type': ''})
        gotcha = tbl_val.get('desc') or (tbl_val.get('warn') and ('; '.join(tbl_val.get('warn')) if isinstance(tbl_val.get('warn'), list) else tbl_val.get('warn'))) or ''
        learned_filter = tbl_val.get('filter', '')
        summary = tbl_val.get('summary', '')
        table_entry = {
            'name': name,
            'schema': schema,
            'columns': cols,
            'gotcha': gotcha,
            'learned_filter': learned_filter,
            'summary': summary,
        }
        tables.append(table_entry)
    
    # Use shared transformation function
    atlas_tables = transform_schema_to_atlas_tables(tables)
    
    from datetime import datetime
    timestamp = datetime.utcnow().isoformat() + 'Z'
    builder.build_connector_atlas(connector_id, connector_type, db_name, atlas_tables, timestamp)

print(f'Built {len(dbs)} atlas files in {builder.atlas_dir}')
