from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.deps import get_current_user
from app.core.tokens import hash_token
from app.models import User, Role, UserInviteToken
from app.schemas import LoginRequest, TokenResponse, RegisterRequest, UserOut, AcceptInviteRequest, ChangePasswordRequest

router = APIRouter()


@router.post("/register")
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Public registration is enabled ONLY for the very first user in the system.
    This first user becomes the Superadmin by default.
    """
    # 1. Count users in DB
    result = await db.execute(select(func.count(User.id)))
    count = result.scalar()

    if count > 0:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Public registration is permanently disabled. Only Superadmins can invite users."
        )

    # 2. Check email uniqueness
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A user with this email already exists.")

    # 3. Create the first user as superadmin
    role_res = await db.execute(select(Role).where(Role.slug == "superadmin"))
    superadmin_role = role_res.scalar_one_or_none()
    role_id = superadmin_role.id if superadmin_role else None

    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        is_superadmin=True,
        force_password_change=False,
        is_active=True,
        token_version=1,
        role_id=role_id,
    )
    db.add(user)
    await db.flush()

    # Log in history
    if role_id:
        from app.models import UserRoleHistory
        db.add(UserRoleHistory(
            user_id=user.id,
            old_role_id=None,
            new_role_id=role_id,
            changed_by=user.id
        ))

    await db.commit()
    return {"message": "First user created as Superadmin successfully."}


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email address")
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    # Embed token_version by passing the user object
    token = create_access_token(user)
    return TokenResponse(access_token=token)


@router.get("/me")
async def me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models import UserManagerAssignment, ConnectorPermission
    from app.core.deps import is_grant_active

    # Check if user has direct reports
    reports_res = await db.execute(
        select(UserManagerAssignment.id).where(
            UserManagerAssignment.manager_user_id == str(current_user.id),
        ).limit(1)
    )
    has_direct_reports = reports_res.scalar_one_or_none() is not None

    # Get connector IDs where user has allow_share_access
    share_res = await db.execute(
        select(ConnectorPermission).where(
            ConnectorPermission.user_id == str(current_user.id),
            ConnectorPermission.allow_share_access == True,
        )
    )
    share_connector_ids = [
        str(p.connector_id) for p in share_res.scalars().all()
        if is_grant_active(p)
    ]

    user_data = UserOut.model_validate(current_user).model_dump()
    user_data["has_direct_reports"] = has_direct_reports
    user_data["share_access_connector_ids"] = share_connector_ids
    return user_data


@router.post('/accept-invite')
async def accept_invite(payload: AcceptInviteRequest, db: AsyncSession = Depends(get_db)):
    # 1. Hash the incoming token
    token_hash = hash_token(payload.token)

    # 2. Look up invite record
    invite = await db.execute(
        select(UserInviteToken).where(
            UserInviteToken.token_hash == token_hash,
            UserInviteToken.used_at.is_(None),
            UserInviteToken.expires_at > datetime.utcnow(),
        )
    )
    invite = invite.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=400, detail="Invalid or expired invite token.")

    # 3. Validate passwords match
    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    # 4. Set password + mark token used + clear force_password_change
    user = await db.get(User, invite.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.hashed_password = hash_password(payload.password)
    user.force_password_change = False
    user.token_version += 1        # invalidate any existing sessions
    invite.used_at = datetime.utcnow()

    await db.commit()
    return {"message": "Password set. You can now log in."}


@router.post('/change-password')
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    current_user.hashed_password = hash_password(payload.new_password)
    current_user.token_version += 1    # invalidate all existing sessions
    current_user.force_password_change = False
    await db.commit()
    return {"message": "Password changed. Please log in again."}
