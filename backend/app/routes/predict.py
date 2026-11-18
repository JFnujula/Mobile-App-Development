import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.authentication.deps import get_current_user, require_admin
from app.schemas.api import CreateUserRequest, ModelInfo, PredictionResult, UserOut
from app.schemas.features import FEATURE_SPECS, PredictionInput
from app.services import user_service
from app.services.model_service import model_service

log = logging.getLogger("app.predict")

router = APIRouter(tags=["Prediction"])
admin_router = APIRouter(prefix="/admin", tags=["Admin"])
health_router = APIRouter(tags=["Health"])


@health_router.get("/health", summary="Liveness / readiness (public, reveals nothing sensitive)")
def health():
    return {"status": "ok" if model_service.ready else "model_not_loaded"}


@router.get("/model/schema", response_model=ModelInfo, summary="Model description + input feature specification")
def model_schema(_user: dict = Depends(get_current_user)):
    """The mobile app builds its input form from `features` - no field is hard-coded in the app."""
    meta = model_service.meta
    feats = []
    for s in FEATURE_SPECS:
        f = dict(s)
        r = meta["training_ranges"][s["column"]]
        f["training_range"] = {"min": r["min"], "max": r["max"], "median": r["median"]}
        feats.append(f)
    return ModelInfo(model_name=meta["model_name"], target=meta["target"],
                     notebook_metrics_test=meta["notebook_metrics_test"], cv_r2_5fold=meta["cv_r2_5fold"],
                     n_train=meta["n_train"], n_test=meta["n_test"], exported_at=meta["exported_at"],
                     versions=meta["versions"], features=feats)


@router.post("/predict", response_model=PredictionResult, summary="Predict relative humidity (RH, %)")
def predict(body: PredictionInput, user: dict = Depends(get_current_user)):  # type: ignore[valid-type]
    if not model_service.ready:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Model not loaded")
    try:
        result = model_service.predict(body.model_dump())          # type: ignore[attr-defined]
    except Exception:
        log.exception("prediction failed user=%s", user["username"])
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Prediction failed")
    log.info("prediction user=%s rh=%.2f", user["username"], result["prediction"])   # inputs are not logged
    return result


# ---- admin (authorization: role == admin) ---------------------------------------------------
@admin_router.post("/users", response_model=UserOut, status_code=201, summary="Create a user")
def create_user(body: CreateUserRequest, _admin: dict = Depends(require_admin)):
    try:
        u = user_service.create_user(body.username, body.password, body.role)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))
    return UserOut(id=u["id"], username=u["username"], role=u["role"], is_active=bool(u["is_active"]))


@admin_router.get("/users", response_model=list[UserOut], summary="List users")
def list_users(_admin: dict = Depends(require_admin)):
    return [UserOut(id=u["id"], username=u["username"], role=u["role"], is_active=bool(u["is_active"]))
            for u in user_service.list_users()]


@admin_router.post("/users/{username}/deactivate", status_code=204, summary="Deactivate a user (effective immediately)")
def deactivate(username: str, admin: dict = Depends(require_admin)):
    if username.lower() == admin["username"].lower():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate yourself")
    if not user_service.set_active(username, False):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
