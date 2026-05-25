import asyncio
import json
import logging
import os
import sys
from datetime import datetime

# Setup paths to import from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.future import select
from app.core.database import AsyncSessionLocal
from app.models import Connector
from app.services.atlas_builder import get_atlas_builder, transform_schema_to_atlas_tables

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("export_atlases")

async def export_atlases():
    """Reads schemas from the DB cache and writes the atlas .json files to disk."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Connector).where(Connector.is_active == True))
        connectors = result.scalars().all()
        
        builder = get_atlas_builder()
        updated_count = 0
        
        for connector in connectors:
            if not connector.schema_cache:
                logger.info(f"Skipping {connector.name} ({connector.id}): No schema cached in DB yet.")
                continue
                
            logger.info(f"Exporting disk Atlas for Connector: {connector.name} ({connector.id})")
            tables = connector.schema_cache.get("tables", [])
            
            # Transform tables to atlas-compatible structure
            atlas_tables = transform_schema_to_atlas_tables(tables)
            
            # Timestamp fallback
            timestamp = connector.schema_cached_at
            if timestamp is None:
                timestamp = datetime.utcnow()
            timestamp_str = timestamp.isoformat() + "Z"
            
            # Build and write the .json file to app/atlas/
            builder.build_connector_atlas(
                connector_id=str(connector.id),
                connector_type=connector.type.value if hasattr(connector.type, 'value') else str(connector.type),
                db_name=connector.name,
                tables=atlas_tables,
                timestamp=timestamp_str
            )
            updated_count += 1
            
        logger.info(f"Export complete! Generated {updated_count} atlas files on disk under {builder.atlas_dir}.")

if __name__ == "__main__":
    asyncio.run(export_atlases())
