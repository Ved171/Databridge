import secrets
import hashlib
from datetime import datetime, timedelta

def generate_invite_token() -> tuple[str, str]:
    """Returns (raw_token, hashed_token). Store hash, email raw."""
    raw = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed

def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

INVITE_TOKEN_TTL_HOURS = 48
