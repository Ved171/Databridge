from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import List
import json
import logging
import os
import uuid
import shutil

from app.core.config import settings

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_superadmin, get_current_admin_or_wsadmin
from app.core.security import encrypt_credential, decrypt_credential
from app.models import User, Connector, ConnectorPermission, ConnectorType
from app.schemas import ConnectorCreate, ConnectorUpdate, ConnectorOut, ConnectorSchemaOut
from app.connectors.registry import get_connector
from app.services.atlas_builder import get_atlas_builder, transform_schema_to_atlas_tables

logger = logging.getLogger(__name__)

router = APIRouter()


async def build_atlas_for_connector(connector: Connector, db: AsyncSession) -> None:
    """
    Build atlas for a connector after it's created or schema is refreshed.
    
    Args:
        connector: The connector object
        db: Database session
    """
    try:
        config = json.loads(decrypt_credential(connector.encrypted_config))
        adapter = get_connector(connector.type, config)
        
        tables = await adapter.get_schema()
        
        # Use shared transformation function from atlas_builder
        atlas_tables = transform_schema_to_atlas_tables(tables)
        
        timestamp = datetime.utcnow().isoformat() + "Z"
        builder = get_atlas_builder()
        builder.build_connector_atlas(
            connector_id=connector.id,
            connector_type=connector.type.value if hasattr(connector.type, 'value') else str(connector.type),
            db_name=connector.name,
            tables=atlas_tables,
            timestamp=timestamp
        )
        logger.info(f"Successfully built atlas for connector {connector.id}")
    except Exception as e:
        logger.error(f"Failed to build atlas for connector {connector.id}: {e}")
        # Don't raise - atlas creation failure shouldn't block connector operations


@router.post("/", response_model=ConnectorOut)
async def create_connector(
    payload: ConnectorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    encrypted = encrypt_credential(json.dumps(payload.config))
    connector = Connector(
        name=payload.name,
        type=payload.type,
        encrypted_config=encrypted,
        workspace_id=payload.workspace_id,
        created_by=current_user.id,
    )
    db.add(connector)
    await db.flush()
    await db.refresh(connector)
    
    # Automatically build atlas after connector creation
    await build_atlas_for_connector(connector, db)
    
    return connector


@router.get("/", response_model=List[ConnectorOut])
async def list_connectors(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_superadmin:
        result = await db.execute(select(Connector).where(Connector.is_active == True))
        return result.scalars().all()

    # Only connectors the user has a permission record for
    result = await db.execute(
        select(Connector)
        .join(ConnectorPermission, ConnectorPermission.connector_id == Connector.id)
        .where(
            ConnectorPermission.user_id == current_user.id,
            Connector.is_active == True,
        )
    )
    return result.scalars().all()


@router.get("/{connector_id}", response_model=ConnectorOut)
async def get_connector_detail(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connector not found")
    return conn


@router.get("/{connector_id}/config")
async def get_connector_config(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connector not found")

    config = json.loads(decrypt_credential(conn.encrypted_config))
    return config


@router.patch("/{connector_id}", response_model=ConnectorOut)
async def update_connector(
    connector_id: str,
    payload: ConnectorUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connector not found")

    if payload.name is not None:
        conn.name = payload.name
    if payload.config is not None:
        conn.encrypted_config = encrypt_credential(json.dumps(payload.config))
        conn.schema_cache = None
        conn.schema_cached_at = None
    if payload.is_active is not None:
        conn.is_active = payload.is_active

    await db.flush()
    await db.refresh(conn)
    return conn


@router.delete("/{connector_id}")
async def delete_connector(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    # Delete atlas before deleting connector
    try:
        builder = get_atlas_builder()
        deleted = builder.delete_connector_atlas(conn.name)
        if deleted:
            logger.info(f"Deleted atlas for connector {conn.name}")
    except Exception as e:
        logger.error(f"Failed to delete atlas for connector {conn.name}: {e}")
        # Don't raise - atlas deletion failure shouldn't block connector deletion
    
    await db.delete(conn)
    return {"status": "deleted"}


@router.post("/{connector_id}/test")
async def test_connection(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connector not found")

    config = json.loads(decrypt_credential(conn.encrypted_config))
    adapter = get_connector(conn.type, config)

    try:
        await adapter.test_connection()
        return {"status": "ok", "message": "Connection successful"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection failed: {str(e)}")


@router.post("/{connector_id}/refresh-schema", response_model=ConnectorSchemaOut)
async def refresh_schema(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_or_wsadmin),
):
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connector not found")

    config = json.loads(decrypt_credential(conn.encrypted_config))
    adapter = get_connector(conn.type, config)

    try:
        tables = await adapter.get_schema()
        schema = [
            {
                "name": t.name,
                "schema": t.schema,
                "row_count": t.row_count,
                "columns": [
                    {"name": c.name, "type": c.type, "nullable": c.nullable, "primary_key": c.primary_key}
                    for c in t.columns
                ],
            }
            for t in tables
        ]
        conn.schema_cache = {"tables": schema}
        conn.schema_cached_at = datetime.utcnow()
        await db.flush()
        
        # Automatically rebuild atlas after schema refresh
        await build_atlas_for_connector(conn, db)
        
        return ConnectorSchemaOut(connector_id=connector_id, tables=schema)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Schema fetch failed: {str(e)}")


@router.get("/{connector_id}/schema", response_model=ConnectorSchemaOut)
async def get_schema(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connector not found")

    if conn.schema_cache:
        return ConnectorSchemaOut(connector_id=connector_id, tables=conn.schema_cache.get("tables", []))

    raise HTTPException(status_code=404, detail="Schema not cached yet. Run refresh-schema first.")


# ─── SQLite File Upload Helpers ──────────────────────────────────────────────

ALLOWED_SQLITE_EXTENSIONS = {".db", ".sqlite", ".sqlite3"}


def _validate_sqlite_file(file: UploadFile) -> str:
    """Validate the uploaded file is a SQLite database. Returns the file extension."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_SQLITE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{ext}'. Allowed: {', '.join(ALLOWED_SQLITE_EXTENSIONS)}"
        )
    return ext


async def _save_sqlite_file(file: UploadFile) -> str:
    """Save uploaded SQLite file to disk. Returns the full path inside the container."""
    max_bytes = settings.SQLITE_MAX_UPLOAD_MB * 1024 * 1024
    upload_dir = settings.SQLITE_UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)

    # Generate unique filename
    ext = os.path.splitext(file.filename)[1].lower()
    safe_name = file.filename.replace(" ", "_").replace("/", "_").replace("\\", "_")
    unique_name = f"{uuid.uuid4().hex[:12]}_{safe_name}"
    dest_path = os.path.join(upload_dir, unique_name)

    # Stream to disk with size check
    total = 0
    try:
        with open(dest_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1 MB chunks
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    f.close()
                    os.remove(dest_path)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum allowed size is {settings.SQLITE_MAX_UPLOAD_MB} MB. "
                               f"For larger files, use the path-based configuration instead."
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    return dest_path


# ─── SQLite Upload Endpoints ─────────────────────────────────────────────────

@router.post("/upload-sqlite", response_model=ConnectorOut)
async def create_sqlite_connector_via_upload(
    name: str = Form(...),
    file: UploadFile = File(...),
    workspace_id: str = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Create a new SQLite connector by uploading a .db file."""
    _validate_sqlite_file(file)
    dest_path = await _save_sqlite_file(file)

    config = {"path": dest_path}
    encrypted = encrypt_credential(json.dumps(config))

    connector = Connector(
        name=name,
        type=ConnectorType.SQLITE,
        encrypted_config=encrypted,
        workspace_id=workspace_id,
        created_by=current_user.id,
    )
    db.add(connector)
    await db.flush()
    await db.refresh(connector)

    # Automatically build atlas after connector creation
    await build_atlas_for_connector(connector, db)

    logger.info(f"SQLite connector created via upload: {name} -> {dest_path}")
    return connector


@router.post("/{connector_id}/upload-sqlite-file", response_model=ConnectorOut)
async def replace_sqlite_file(
    connector_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_or_wsadmin),
):
    """Replace the SQLite file for an existing connector."""
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connector not found")
    if conn.type != ConnectorType.SQLITE:
        raise HTTPException(status_code=400, detail="Connector is not a SQLite connector")

    _validate_sqlite_file(file)

    # Delete old file if it exists in the upload directory
    try:
        old_config = json.loads(decrypt_credential(conn.encrypted_config))
        old_path = old_config.get("path", "")
        if old_path and old_path.startswith(settings.SQLITE_UPLOAD_DIR) and os.path.exists(old_path):
            os.remove(old_path)
            logger.info(f"Deleted old SQLite file: {old_path}")
    except Exception as e:
        logger.warning(f"Could not clean up old file: {e}")

    # Save new file
    dest_path = await _save_sqlite_file(file)

    config = {"path": dest_path}
    conn.encrypted_config = encrypt_credential(json.dumps(config))
    conn.schema_cache = None
    conn.schema_cached_at = None
    await db.flush()
    await db.refresh(conn)

    # Rebuild atlas
    await build_atlas_for_connector(conn, db)

    logger.info(f"SQLite file replaced for connector {connector_id}: {dest_path}")
    return conn

