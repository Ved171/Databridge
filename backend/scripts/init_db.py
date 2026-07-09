import asyncio
import os
import sys

# Add backend root to path to resolve app.* imports correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import engine, Base
import app.models

async def init_db():
    print("Creating database tables using SQLAlchemy metadata...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully.")

if __name__ == "__main__":
    asyncio.run(init_db())
