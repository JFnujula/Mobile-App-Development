import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import get_settings
from app.db import init_db
from app.routes import auth
from app.routes.predict import admin_router, health_router, router as predict_router
from app.services import user_service
from app.services.model_service import model_service
from app.utils.logging_setup import setup_logging

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    s = get_settings()
    setup_logging(s.log_level)
    log = logging.getLogger("app")
    init_db()
    user_service.bootstrap_admin()
    model_service.load()                       # model.pkl is loaded ONCE, at start-up
    log.info("Ready (environment=%s)", s.environment)
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="Relative Humidity Prediction API (private)",
        version="1.0.0",
        description="Serves the notebook's Polynomial Regression (degree 3) model. All endpoints except /health require a Bearer token.",
        lifespan=lifespan,
        docs_url="/docs" if s.enable_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if s.enable_docs else None,
    )

    if s.allowed_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=s.allowed_hosts)
    if s.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_methods=["GET", "POST"],
                           allow_headers=["Authorization", "Content-Type"], allow_credentials=False)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        if s.enforce_https and request.headers.get("x-forwarded-proto", request.url.scheme) != "https" \
                and request.url.path != "/health":
            return RedirectResponse(str(request.url.replace(scheme="https")), status_code=308)
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["Referrer-Policy"] = "no-referrer"
        if s.enforce_https:
            resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return resp

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_req: Request, exc: RequestValidationError):
        errors = []
        for e in exc.errors():
            loc = [str(p) for p in e["loc"] if p not in ("body", "query")]
            errors.append({"field": ".".join(loc) or None, "message": e["msg"].replace("Value error, ", "")})
        return JSONResponse(status_code=422, content={"detail": "Validation failed", "errors": errors})

    @app.exception_handler(Exception)
    async def unhandled(_req: Request, exc: Exception):
        logging.getLogger("app").exception("unhandled error")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.include_router(health_router)                               # /health (public)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(predict_router, prefix=API_PREFIX)
    app.include_router(admin_router, prefix=API_PREFIX)
    return app


app = create_app()
