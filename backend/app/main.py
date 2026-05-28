from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog

from app.core.config import settings
from app.core.database import engine, Base
from app.api.routes import auth, workspaces, connectors, permissions, query, users

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("DataBridge starting up", environment=settings.ENVIRONMENT)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Auto-migrate rls_policies columns if they are missing
        try:
            from sqlalchemy import text
            is_postgres = "postgresql" in str(engine.url)
            if is_postgres:
                await conn.execute(text("ALTER TABLE rls_policies ADD COLUMN IF NOT EXISTS filter_expr_nosql JSON;"))
                await conn.execute(text("ALTER TABLE rls_policies ALTER COLUMN filter_expr DROP NOT NULL;"))
                logger.info("PostgreSQL rls_policies auto-migration succeeded")
            else:
                try:
                    await conn.execute(text("ALTER TABLE rls_policies ADD COLUMN filter_expr_nosql JSON;"))
                    logger.info("SQLite/Other rls_policies auto-migration succeeded")
                except Exception:
                    # Column might already exist
                    pass
        except Exception as e:
            logger.warning("Auto-migration of rls_policies failed", error=str(e))
            
    yield
    logger.info("DataBridge shutting down")


app = FastAPI(
    title="DataBridge",
    description="Internal AI Data Gateway -- Connect any DB, query with natural language",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,        prefix="/api/auth",        tags=["Auth"])
app.include_router(users.router,       prefix="/api/users",       tags=["Users"])
app.include_router(workspaces.router,  prefix="/api/workspaces",  tags=["Workspaces"])
app.include_router(connectors.router,  prefix="/api/connectors",  tags=["Connectors"])
app.include_router(permissions.router, prefix="/api/permissions", tags=["Permissions"])
app.include_router(query.router,       prefix="/api/query",       tags=["Query"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "DataBridge"}
