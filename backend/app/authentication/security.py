"""Password hashing (bcrypt), JWT creation/validation, login throttling."""
from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import get_settings

# A valid bcrypt hash of a random string: compared against when the username does not exist so that
# response time does not reveal which usernames are registered.
_DUMMY_HASH = bcrypt.hashpw(uuid.uuid4().hex.encode(), bcrypt.gensalt(rounds=12))


def hash_password(password: str) -> str:
    # bcrypt only uses the first 72 bytes; reject longer input instead of silently truncating
    pw = password.encode()
    if len(pw) > 72:
        raise ValueError("Password must be at most 72 bytes")
    return bcrypt.hashpw(pw, bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        target = password_hash.encode() if password_hash else _DUMMY_HASH
        ok = bcrypt.checkpw(password.encode()[:72], target)
        return ok and password_hash is not None
    except ValueError:
        return False


def _create_token(sub: str, token_type: str, lifetime: timedelta, extra: dict | None = None) -> tuple[str, str, int]:
    s = get_settings()
    now = datetime.now(timezone.utc)
    jti = uuid.uuid4().hex
    exp = now + lifetime
    payload = {"sub": sub, "type": token_type, "jti": jti, "iat": now, "exp": exp, **(extra or {})}
    return jwt.encode(payload, s.secret_key, algorithm=s.jwt_algorithm), jti, int(exp.timestamp())


def create_access_token(username: str, role: str) -> tuple[str, int]:
    s = get_settings()
    tok, _, _ = _create_token(username, "access", timedelta(minutes=s.access_token_minutes), {"role": role})
    return tok, s.access_token_minutes * 60


def create_refresh_token(username: str) -> str:
    s = get_settings()
    tok, _, _ = _create_token(username, "refresh", timedelta(days=s.refresh_token_days))
    return tok


def decode_token(token: str, expected_type: str) -> dict:
    """Raises jwt.PyJWTError on any problem (bad signature, expired, wrong type...)."""
    s = get_settings()
    payload = jwt.decode(token, s.secret_key, algorithms=[s.jwt_algorithm],
                         options={"require": ["exp", "sub", "type", "jti"]})
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


class LoginThrottle:
    """In-memory limiter: N failures per (username, ip) -> locked for M minutes.
    For multi-process deployments, use a shared store (Redis) or a reverse-proxy rate limit as well."""

    def __init__(self) -> None:
        self._fails: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _key(self, username: str, ip: str) -> str:
        return f"{username.lower()}|{ip}"

    def is_locked(self, username: str, ip: str) -> int:
        """Returns seconds remaining if locked, else 0."""
        s = get_settings()
        window = s.login_lockout_minutes * 60
        now = time.time()
        with self._lock:
            hits = [t for t in self._fails.get(self._key(username, ip), []) if now - t < window]
            self._fails[self._key(username, ip)] = hits
            if len(hits) >= s.login_max_attempts:
                return int(window - (now - hits[0])) + 1
        return 0

    def register_failure(self, username: str, ip: str) -> None:
        with self._lock:
            self._fails.setdefault(self._key(username, ip), []).append(time.time())

    def reset(self, username: str, ip: str) -> None:
        with self._lock:
            self._fails.pop(self._key(username, ip), None)


login_throttle = LoginThrottle()
