import secrets
import json
import redis  # type: ignore
from app.core.config import settings

TOKEN_TTL_SECONDS = 300          # 5 minutes to complete login
STATUS_TTL_SECONDS = 1800        # 30 minutes — status stays queryable well past token expiry

_TOKEN_KEY_PREFIX = "connect_token:"
_STATUS_KEY_PREFIX = "connect_status:"
_ACTIVE_TOKEN_KEY_PREFIX = "connect_active:"  # tracks the current active token per user


def _get_redis() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def create_token(user_id: int) -> str:
    """
    Generates a new one-time connect-token for this user.
    Invalidates any previous still-pending token for the same user first,
    so only one connection attempt can be active at a time.
    """
    r = _get_redis()

    # Invalidate any previous active token for this user
    previous_token = r.get(f"{_ACTIVE_TOKEN_KEY_PREFIX}{user_id}")
    if previous_token:
        r.delete(f"{_TOKEN_KEY_PREFIX}{previous_token}")

    token = secrets.token_urlsafe(32)

    r.setex(f"{_TOKEN_KEY_PREFIX}{token}", TOKEN_TTL_SECONDS, str(user_id))
    r.setex(f"{_ACTIVE_TOKEN_KEY_PREFIX}{user_id}", TOKEN_TTL_SECONDS, token)

    set_status(token, "pending", "Waiting for LinkedIn login...")

    return token


def redeem_token(token: str) -> int | None:
    """
    Validates and consumes a connect-token. Returns the associated user_id
    if valid, or None if the token is missing, expired, or already used.
    The token is deleted immediately on redemption (single-use).
    """
    r = _get_redis()
    key = f"{_TOKEN_KEY_PREFIX}{token}"

    user_id = r.get(key)
    if not user_id:
        return None

    r.delete(key)  # single-use: gone immediately after redemption
    return int(user_id)


def set_status(token: str, status: str, detail: str = "") -> None:
    r = _get_redis()
    r.setex(
        f"{_STATUS_KEY_PREFIX}{token}",
        STATUS_TTL_SECONDS,
        json.dumps({"status": status, "detail": detail}),
    )


def get_status(token: str) -> dict:
    r = _get_redis()
    raw = r.get(f"{_STATUS_KEY_PREFIX}{token}")
    if not raw:
        return {"status": "unknown", "detail": "Token not found or expired."}
    return json.loads(raw)