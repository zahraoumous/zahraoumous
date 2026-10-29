import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, Request, Response
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import delete, insert, select

from app.core.config import get_settings
from app.features.db import get_engine
from app.features.tables import feature_sessions
from app.models import users

COOKIE_NAME = "dp_session"
SESSION_SECONDS = 7 * 24 * 3600
# Explicit, versioned parameters permit safe future password-hash migration.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 32768, 8, 3
SCRYPT_MAXMEM = 64 * 1024 * 1024


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    result = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        maxmem=SCRYPT_MAXMEM,
        dklen=32,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${result.hex()}"


# Equal-cost check when an email is unknown, reducing account timing disclosure.
DUMMY_HASH = hash_password("not-a-user-password")


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt, expected = encoded.split("$")
        if scheme != "scrypt" or (int(n), int(r), int(p)) != (SCRYPT_N, SCRYPT_R, SCRYPT_P):
            return False
        actual = hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            maxmem=SCRYPT_MAXMEM,
            dklen=32,
        )
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError, UnicodeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def require_origin(request: Request) -> None:
    # Applies to login/register too: login CSRF must not fix a browser to an attacker's account.
    origin = request.headers.get("origin", "")
    expected = get_settings().app_origin.rstrip("/")
    allowed = {expected}
    if expected == "http://localhost:3000":
        allowed.add("http://127.0.0.1:3000")
    if origin not in allowed:
        raise HTTPException(403, "Request origin is not allowed")


def rate_limit(request: Request, email: str) -> None:
    address = request.client.host if request.client else "unknown"
    keys = [("ip:" + address, 100), ("email:" + email, 20)]
    try:
        with Redis.from_url(
            get_settings().redis_url.get_secret_value(), socket_timeout=3, socket_connect_timeout=3
        ) as client:
            for value, limit in keys:
                key = "dp:auth:" + hashlib.sha256(value.encode()).hexdigest()
                with client.pipeline(transaction=True) as pipeline:
                    pipeline.incr(key)
                    pipeline.expire(key, 300, nx=True)
                    count, _ = pipeline.execute()
                if count > limit:
                    raise HTTPException(429, "Too many attempts. Try again in five minutes.")
    except RedisError:
        raise HTTPException(503, "Authentication is temporarily unavailable") from None


def add_session(connection, user_id, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    connection.execute(
        insert(feature_sessions).values(
            token_hash=token_hash(token),
            user_id=user_id,
            expires_at=datetime.now(UTC) + timedelta(seconds=SESSION_SECONDS),
        )
    )
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_SECONDS,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def current_user(request: Request) -> dict[str, Any]:
    token = request.cookies.get(COOKIE_NAME)
    if not token or len(token) > 256:
        raise HTTPException(401, "Sign in to continue")
    with get_engine().connect() as connection:
        record = (
            connection.execute(
                select(users.c.id, users.c.email, users.c.display_name)
                .select_from(users.join(feature_sessions, users.c.id == feature_sessions.c.user_id))
                .where(
                    feature_sessions.c.token_hash == token_hash(token),
                    feature_sessions.c.expires_at > datetime.now(UTC),
                )
            )
            .mappings()
            .first()
        )
    if record is None:
        raise HTTPException(401, "Session expired. Sign in again")
    return dict(record)


def remove_session(request: Request, response: Response) -> None:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        with get_engine().begin() as connection:
            connection.execute(
                delete(feature_sessions).where(feature_sessions.c.token_hash == token_hash(token))
            )
    response.delete_cookie(
        COOKIE_NAME, path="/", samesite="strict", secure=get_settings().cookie_secure, httponly=True
    )
    response.headers["Cache-Control"] = "no-store"
