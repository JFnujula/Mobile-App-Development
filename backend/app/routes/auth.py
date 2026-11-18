import logging

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.authentication.deps import get_current_user, oauth2_scheme
from app.authentication.security import (create_access_token, create_refresh_token, decode_token,
                                         login_throttle)
from app.schemas.api import RefreshRequest, TokenPair, UserOut
from app.services import user_service

log = logging.getLogger("app.auth")
router = APIRouter(prefix="/auth", tags=["Authentication"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _issue(user) -> TokenPair:
    access, ttl = create_access_token(user["username"], user["role"])
    return TokenPair(access_token=access, refresh_token=create_refresh_token(user["username"]), expires_in=ttl)


@router.post("/login", response_model=TokenPair, summary="Log in with username and password")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    ip = _client_ip(request)
    wait = login_throttle.is_locked(form.username, ip)
    if wait:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            detail=f"Too many failed attempts. Try again in {wait // 60 + 1} minute(s).",
                            headers={"Retry-After": str(wait)})
    user = user_service.authenticate(form.username, form.password)
    if not user:
        login_throttle.register_failure(form.username, ip)
        log.warning("failed login username=%s ip=%s", form.username[:40], ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    login_throttle.reset(form.username, ip)
    log.info("login ok username=%s ip=%s", user["username"], ip)
    return _issue(user)


@router.post("/refresh", response_model=TokenPair, summary="Exchange a refresh token for a new token pair")
def refresh(body: RefreshRequest):
    bad = HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    try:
        payload = decode_token(body.refresh_token, "refresh")
    except jwt.PyJWTError:
        raise bad
    if user_service.is_revoked(payload["jti"]):
        raise bad
    user = user_service.get_user(payload["sub"])
    if not user or not user["is_active"]:
        raise bad
    user_service.revoke_token(payload["jti"], int(payload["exp"]))      # rotation: one use only
    return _issue(user)


@router.post("/logout", status_code=204, summary="Revoke the refresh token (and current access token)")
def logout(body: RefreshRequest, token: str = Depends(oauth2_scheme), _user: dict = Depends(get_current_user)):
    for tok, kind in ((body.refresh_token, "refresh"), (token, "access")):
        try:
            p = decode_token(tok, kind)
            user_service.revoke_token(p["jti"], int(p["exp"]))
        except jwt.PyJWTError:
            pass


@router.get("/me", response_model=UserOut, summary="Current user")
def me(user: dict = Depends(get_current_user)):
    return UserOut(**user)
