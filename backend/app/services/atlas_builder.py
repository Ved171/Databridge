"""
app/services/atlas_builder.py
─────────────────────────────
Build per-connector atlas files (Iceberg-style) from the full schema.

Instead of one giant 1.4MB databridge_schema_summary.json that loads
on every cold start, we create:
  - atlas/
    - postgres-prod.json
    - mysql-warehouse.json
    - snowflake-analytics.json
    - ...

Each atlas file contains the full table/column metadata for ONE connector,
loaded on-demand or at startup and held in memory.

Run this script:
  1. When the server starts (load all atlases once)
  2. When sync_schema.py runs (rebuild single connector atlas)
  3. Via API endpoint for manual refresh
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class AtlasMetadata:
    """Metadata for a single connector's atlas file."""
    connector_id: str
    connector_type: str
    db_name: str
    table_count: int
    last_updated: str  # ISO format timestamp
    schema_version: str = "1.0"


class AtlasBuilder:
    """
    Builds and manages per-connector atlas files.
    
    Atlas structure (one file per connector):
    ```json
    {
        "metadata": {
            "connector_id": "pg-prod",
            "connector_type": "postgres",
            "db_name": "production",
            "table_count": 42,
            "last_updated": "2025-05-22T14:30:00Z"
        },
        "tables": [
            {
                "name": "users",
                "schema": "public",
                "columns": [
                    {"name": "id", "type": "INT", "semantic_type": "id"},
                    {"name": "email", "type": "VARCHAR", "semantic_type": "email"}
                ],
                "gotcha": "Soft-deleted via 'deleted_at' column",
                "learned_filter": "WHERE deleted_at IS NULL",
                "summary": "User accounts and authentication"
            }
        ]
    }
    ```
    """
    
    def __init__(self, atlas_dir: Optional[Path] = None):
        """
        Initialize the atlas builder.
        
        Args:
            atlas_dir: Directory to store atlas files. Defaults to app/atlas/
        """
        if atlas_dir is None:
            # Infer from this file location: app/services/atlas_builder.py -> app/atlas/
            app_dir = Path(__file__).resolve().parent.parent
            atlas_dir = app_dir / "atlas"
        
        self.atlas_dir = Path(atlas_dir)
        self.atlas_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Atlas directory: {self.atlas_dir}")
    
    def _get_atlas_path(self, db_name: str) -> Path:
        """Get the file path for a connector's atlas using database name."""
        # Sanitize db_name to a safe filename
        safe_name = db_name.replace("/", "_").replace("\\", "_").strip()
        return self.atlas_dir / f"{safe_name}.json"
    
    def build_connector_atlas(
        self,
        connector_id: str,
        connector_type: str,
        db_name: str,
        tables: List[Dict[str, Any]],
        timestamp: str,
    ) -> Path:
        """
        Build and save an atlas file for a single connector.
        
        Args:
            connector_id: Unique ID of the connector.
            connector_type: Type (postgres, mysql, mongodb, etc.).
            db_name: Human-readable database name.
            tables: List of table dicts with schema metadata.
            timestamp: ISO format timestamp.
            
        Returns:
            Path to the saved atlas file.
        """
        metadata = AtlasMetadata(
            connector_id=connector_id,
            connector_type=connector_type,
            db_name=db_name,
            table_count=len(tables),
            last_updated=timestamp,
        )
        
        atlas = {
            "metadata": asdict(metadata),
            "tables": tables,
        }
        
        path = self._get_atlas_path(db_name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(atlas, f, indent=2)
        
        logger.info(f"Built atlas for {db_name}: {len(tables)} tables -> {path}")
        return path
    
    def load_connector_atlas(self, db_name: str) -> Optional[Dict[str, Any]]:
        """
        Load an atlas file for a connector from disk.
        
        Args:
            db_name: The database name.
            
        Returns:
            The parsed atlas dict, or None if not found.
        """
        path = self._get_atlas_path(db_name)
        if not path.exists():
            logger.warning(f"Atlas file not found: {path}")
            return None
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                atlas = json.load(f)
            logger.debug(f"Loaded atlas for {db_name} from {path}")
            return atlas
        except Exception as e:
            logger.error(f"Failed to load atlas {path}: {e}")
            return None
    
    def load_connector_atlas_by_id(self, connector_id: str) -> Optional[Dict[str, Any]]:
        """
        Load an atlas file by connector ID (scans all atlases to find matching ID).
        
        Args:
            connector_id: The connector ID to search for.
            
        Returns:
            The parsed atlas dict, or None if not found.
        """
        for path in self.list_atlas_files():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    atlas = json.load(f)
                atlas_connector_id = atlas.get("metadata", {}).get("connector_id")
                if atlas_connector_id == connector_id:
                    logger.debug(f"Loaded atlas for connector_id {connector_id} from {path}")
                    return atlas
            except Exception as e:
                logger.error(f"Failed to load atlas {path}: {e}")
        
        logger.warning(f"No atlas found for connector_id {connector_id}")
        return None
    
    def list_atlas_files(self) -> List[Path]:
        """List all atlas files in the atlas directory."""
        return sorted(self.atlas_dir.glob("*.json"))
    
    def load_all_atlases(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all atlas files from disk into memory.
        
        Returns:
            Dict keyed by connector_id, values are parsed atlas dicts.
        """
        result = {}
        for path in self.list_atlas_files():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    atlas = json.load(f)
                connector_id = atlas.get("metadata", {}).get("connector_id")
                if connector_id:
                    result[connector_id] = atlas
                    logger.debug(f"Loaded atlas: {connector_id}")
            except Exception as e:
                logger.error(f"Failed to load atlas {path}: {e}")
        
        logger.info(f"Loaded {len(result)} atlases")
        return result
    
    def delete_connector_atlas(self, db_name: str) -> bool:
        """
        Delete an atlas file (called when connector is removed).
        
        Args:
            db_name: The database name.
            
        Returns:
            True if deleted, False if not found.
        """
        path = self._get_atlas_path(db_name)
        if path.exists():
            path.unlink()
            logger.info(f"Deleted atlas: {path}")
            return True
        return False


# Global instance (initialized at app startup)
_atlas_builder: Optional[AtlasBuilder] = None


def get_atlas_builder() -> AtlasBuilder:
    """Get or initialize the global atlas builder."""
    global _atlas_builder
    if _atlas_builder is None:
        _atlas_builder = AtlasBuilder()
    return _atlas_builder


def rebuild_atlas_for_connector(
    connector_id: str,
    connector_type: str,
    db_name: str,
    tables: List[Dict[str, Any]],
    timestamp: Optional[str] = None,
) -> None:
    """
    Convenience function to rebuild an atlas file.
    
    Called from sync_schema.py or admin endpoints.
    """
    if timestamp is None:
        from datetime import datetime
        timestamp = datetime.utcnow().isoformat() + "Z"
    
    builder = get_atlas_builder()
    builder.build_connector_atlas(connector_id, connector_type, db_name, tables, timestamp)


def transform_schema_to_atlas_tables(tables: List[Any]) -> List[Dict[str, Any]]:
    """
    Transform connector schema objects to atlas table format.
    
    This is a shared function used by both:
    - create_atlases.py (for bulk creation from JSON)
    - connector routes (for individual connector creation from live DB)
    
    Args:
        tables: List of table schema objects (from connector adapter or JSON)
        
    Returns:
        List of table dicts in atlas format
    """
    atlas_tables = []
    for t in tables:
        # Handle different input formats
        if isinstance(t, dict):
            # From JSON format (create_atlases.py)
            name = t.get('name', '')
            schema = t.get('schema', '')
            columns = t.get('columns', [])
            gotcha = t.get('gotcha', '')
            learned_filter = t.get('learned_filter', '')
            summary = t.get('summary', '')
        else:
            # From live connector schema (connector routes)
            name = t.name
            schema = t.schema
            columns = [
                {"name": c.name, "type": c.type, "nullable": c.nullable, "primary_key": c.primary_key}
                for c in t.columns
            ]
            gotcha = ""
            learned_filter = ""
            summary = ""
        
        atlas_tables.append({
            "name": name,
            "schema": schema,
            "columns": columns,
            "gotcha": gotcha,
            "learned_filter": learned_filter,
            "summary": summary,
        })
    
    return atlas_tables
