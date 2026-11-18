import logging

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.authentication.security import decode_token
from app.services import user_service

log = logging.getLogger("app.auth")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

_UNAUTH = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired credentials",
                        headers={"WWW-Authenticate": "Bearer"})


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Validates the Bearer access token AND re-checks the user in the DB on every request
    (so deactivating a user takes effect immediately)."""
    try:
        payload = decode_token(token, "access")
    except jwt.PyJWTError:
        raise _UNAUTH
    if user_service.is_revoked(payload["jti"]):
        raise _UNAUTH
    user = user_service.get_user(payload["sub"])
    if not user or not user["is_active"]:
        raise _UNAUTH
    return {"id": user["id"], "username": user["username"], "role": user["role"], "is_active": True}


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required")
    return user
