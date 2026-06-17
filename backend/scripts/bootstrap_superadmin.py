import asyncio
import os
import sys

# Add backend root to path to resolve app.* imports correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import AsyncSessionLocal
from app.models import User, Role
from app.core.security import hash_password
from sqlalchemy import select

async def bootstrap():
    email = os.environ.get("SUPERADMIN_EMAIL")
    password = os.environ.get("SUPERADMIN_PASSWORD")
    if not email or not password:
        print("Error: SUPERADMIN_EMAIL and SUPERADMIN_PASSWORD environment variables must be set.")
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(User).where(User.is_superadmin == True)
        )
        if existing.scalar_one_or_none():
            print("Superadmin already exists. Skipping.")
            return

        # Fetch superadmin role if it exists (F-03 default roles seeded)
        role_res = await db.execute(select(Role).where(Role.slug == "superadmin"))
        superadmin_role = role_res.scalar_one_or_none()
        role_id = superadmin_role.id if superadmin_role else None

        user = User(
            email=email,
            name="Super Admin",
            hashed_password=hash_password(password),
            is_superadmin=True,
            force_password_change=True,
            token_version=1,
            is_active=True,
            role_id=role_id,
        )
        db.add(user)
        await db.flush()

        # Log in history if role found
        if role_id:
            from app.models import UserRoleHistory
            db.add(UserRoleHistory(
                user_id=user.id,
                old_role_id=None,
                new_role_id=role_id,
                changed_by=user.id
            ))
            
        await db.commit()
        print(f"Superadmin created: {user.email}")

if __name__ == "__main__":
    asyncio.run(bootstrap())
