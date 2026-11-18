import logging
import sqlite3
import time
from typing import Optional

from app.authentication.security import hash_password, verify_password
from app.config import get_settings
from app.db import get_conn

log = logging.getLogger("app.users")


def get_user(username: str) -> Optional[sqlite3.Row]:
    with get_conn() as c:
        return c.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def list_users() -> list[sqlite3.Row]:
    with get_conn() as c:
        return c.execute("SELECT id, username, role, is_active FROM users ORDER BY id").fetchall()


def create_user(username: str, password: str, role: str = "user") -> sqlite3.Row:
    if len(password) < 10:
        raise ValueError("Password must have at least 10 characters")
    with get_conn() as c:
        try:
            c.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                      (username, hash_password(password), role))
        except sqlite3.IntegrityError as e:
            raise ValueError("Username already exists") from e
    log.info("user created username=%s role=%s", username, role)
    return get_user(username)  # type: ignore[return-value]


def set_active(username: str, active: bool) -> bool:
    with get_conn() as c:
        return c.execute("UPDATE users SET is_active=? WHERE username=?", (int(active), username)).rowcount > 0


def set_password(username: str, password: str) -> bool:
    if len(password) < 10:
        raise ValueError("Password must have at least 10 characters")
    with get_conn() as c:
        return c.execute("UPDATE users SET password_hash=? WHERE username=?",
                         (hash_password(password), username)).rowcount > 0


def authenticate(username: str, password: str) -> Optional[sqlite3.Row]:
    user = get_user(username)
    ok = verify_password(password, user["password_hash"] if user else None)
    if user and ok and user["is_active"]:
        return user
    return None


def revoke_token(jti: str, exp: int) -> None:
    with get_conn() as c:
        c.execute("DELETE FROM revoked_tokens WHERE expires_at < ?", (int(time.time()),))
        c.execute("INSERT OR IGNORE INTO revoked_tokens (jti, expires_at) VALUES (?,?)", (jti, exp))


def is_revoked(jti: str) -> bool:
    with get_conn() as c:
        return c.execute("SELECT 1 FROM revoked_tokens WHERE jti=?", (jti,)).fetchone() is not None


def bootstrap_admin() -> None:
    """Create the first admin from ADMIN_USERNAME / ADMIN_PASSWORD, only if there are no users yet."""
    s = get_settings()
    if not (s.admin_username and s.admin_password):
        return
    with get_conn() as c:
        n = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if n == 0:
        create_user(s.admin_username, s.admin_password, "admin")
        log.warning("Bootstrap admin '%s' created. Remove ADMIN_PASSWORD from the environment now.", s.admin_username)
