from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog

from app.core.config import settings
from app.core.database import engine, Base
from app.api.routes import (
    auth, workspaces, connectors, permissions, query, users,
    dashboard, departments, notifications, packages, rls, roles, scoped_admin,
    oauth
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("DataBridge starting up", environment=settings.ENVIRONMENT)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Ensure SQLite upload directory exists
    import os
    sqlite_dir = settings.SQLITE_UPLOAD_DIR
    os.makedirs(sqlite_dir, exist_ok=True)
    logger.info("SQLite upload directory ready", path=sqlite_dir)
            
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
        "http://192.168.3.83:5173",
        "http://192.168.2.149:5178",
        "https://chat.synovergetech.com:8091",
        "https://chat.synovergetech.com",
        "http://192.168.3.222:5173",
	"https://databridge.synovergetech.com:5178"

    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,        prefix="/api/auth",        tags=["Auth"])
app.include_router(users.router,       prefix="/api/users",       tags=["Users"])
app.include_router(workspaces.router,  prefix="/api/workspaces",  tags=["Workspaces"])
app.include_router(connectors.router,  prefix="/api/connectors",  tags=["Connectors"])
app.include_router(scoped_admin.router, prefix="/api/connectors", tags=["Scoped Admin"])
app.include_router(permissions.router, prefix="/api/permissions", tags=["Permissions"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(query.router,       prefix="/api/query",       tags=["Query"])
app.include_router(departments.router, prefix="/api/departments", tags=["Departments"])
app.include_router(roles.router,       prefix="/api/roles",       tags=["Roles"])
app.include_router(rls.router,         prefix="/api/rls",         tags=["RLS"])
app.include_router(packages.router,    prefix="/api/packages",    tags=["Packages"])
app.include_router(dashboard.router,   prefix="/api/dashboard",   tags=["Dashboard"])
app.include_router(oauth.router,       prefix="",                 tags=["OAuth"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "DataBridge"}
