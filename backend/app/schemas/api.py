from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access-token lifetime in seconds")


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.@-]+$")
    password: str = Field(min_length=10, max_length=128)
    role: str = Field("user", pattern="^(user|admin)$")


class FeatureWarning(BaseModel):
    feature: str
    message: str


class PredictionResult(BaseModel):
    prediction: float = Field(description="Predicted relative humidity (%) - the raw model output")
    target: str = "RH"
    target_label: str = "Relative Humidity"
    unit: str = "%"
    model_name: str
    notebook_test_mae: float = Field(description="Mean absolute error on the notebook's held-out test set (percentage points)")
    notebook_test_rmse: float
    notebook_test_r2: float
    explanation: str
    warnings: List[FeatureWarning] = []
    imputed_features: List[str] = Field(default=[], description="Optional inputs left empty; the training median was used")
    capped_features: List[str] = Field(default=[], description="Inputs beyond the training IQR limits; the pipeline clips them")
    inputs_used: Dict[str, Optional[float]]


class ModelInfo(BaseModel):
    model_name: str
    target: Dict[str, Any]
    notebook_metrics_test: Dict[str, float]
    cv_r2_5fold: Dict[str, float]
    n_train: int
    n_test: int
    exported_at: str
    versions: Dict[str, str]
    features: List[Dict[str, Any]]
