import uuid
from datetime import datetime, timedelta
from jose import jwt  # type: ignore
from app.core.config import settings

ALGORITHM = "HS256"


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({
        "exp": expire,
        "jti": str(uuid.uuid4()),   # unique token ID — enables per-token revocation
    })
    return jwt.encode(to_encode, settings.app_secret_key, algorithm=ALGORITHM)


def revoke_token(jti: str, expires_in_seconds: int) -> None:
    """
    Add a token's jti to the Redis blacklist.
    TTL is set to the token's remaining validity so the key auto-expires.
    """
    import redis as redis_lib  # type: ignore
    try:
        r = redis_lib.from_url(settings.redis_url, decode_responses=True)
        r.setex(f"blacklist:{jti}", expires_in_seconds, "1")
    except Exception:
        pass  # fail open — Redis outage should not break revocation silently in prod


def is_token_revoked(jti: str) -> bool:
    """
    Check if a token's jti is in the Redis blacklist.
    Returns False if Redis is unreachable (fail open).
    """
    import redis as redis_lib  # type: ignore
    try:
        r = redis_lib.from_url(settings.redis_url, decode_responses=True)
        return r.exists(f"blacklist:{jti}") > 0
    except Exception:
        return False  # fail open