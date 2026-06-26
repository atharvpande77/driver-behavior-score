from datetime import datetime, timedelta, timezone
import hashlib

import bcrypt
from jose import JWTError, jwt

from src.core.config import app_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(
        password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )


def create_token(*, subject: str, token_type: str, expires_in_seconds: int, jti: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "typ": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
    }
    if jti is not None:
        payload["jti"] = jti
    secret = app_settings.JWT_REFRESH_SECRET if token_type == "refresh" else app_settings.JWT_SECRET
    return jwt.encode(payload, secret, algorithm=app_settings.JWT_ALGORITHM)


def decode_token(token: str, token_type: str = "access") -> dict | None:
    try:
        secret = app_settings.JWT_REFRESH_SECRET if token_type == "refresh" else app_settings.JWT_SECRET
        return jwt.decode(
            token,
            secret,
            algorithms=[app_settings.JWT_ALGORITHM],
        )
    except JWTError:
        return None


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
