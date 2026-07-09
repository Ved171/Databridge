from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet, InvalidToken
import base64
import hashlib

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _get_fernet() -> Fernet:
    """Derive a valid 32-byte Fernet key from ENCRYPTION_KEY."""
    key_bytes = hashlib.sha256(settings.ENCRYPTION_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def _get_fernet_keys() -> list[str]:
    """Return the active and legacy keys that may be used for decrypting credentials."""
    keys: list[str] = []
    for key in (getattr(settings, "ENCRYPTION_KEY", None), getattr(settings, "LEGACY_ENCRYPTION_KEY", None)):
        if key and key not in keys:
            keys.append(key)
    return keys


def _get_fernet_for_key(key: str) -> Fernet:
    key_bytes = hashlib.sha256(key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_or_data: any, expires_delta: Optional[timedelta] = None) -> str:
    if hasattr(user_or_data, "id") and hasattr(user_or_data, "token_version"):
        to_encode = {
            "sub": str(user_or_data.id),
            "token_version": user_or_data.token_version,
        }
    else:
        to_encode = user_or_data.copy()
        
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def encrypt_credential(value: str) -> str:
    """Encrypt a connector credential for safe DB storage."""
    f = _get_fernet()
    return f.encrypt(value.encode()).decode()


def decrypt_credential(value: str) -> str:
    """Decrypt a stored connector credential.

    If the stored string is legacy plaintext or the key has changed,
    try the configured legacy key(s) before falling back to the raw value.
    """
    if not value:
        return value

    for key in _get_fernet_keys():
        try:
            f = _get_fernet_for_key(key)
            return f.decrypt(value.encode()).decode()
        except (InvalidToken, TypeError, ValueError):
            continue

    return value
