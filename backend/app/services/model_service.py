"""Loads the pickled pipeline once at start-up and serves predictions from it.

Nothing here re-implements preprocessing: the loaded object is the notebook's full Pipeline
(median imputation -> IQR capping -> StandardScaler -> PolynomialFeatures(3) -> LinearRegression),
so inference applies exactly the transformations learned on the training set.
"""
from __future__ import annotations

import json
import logging
import warnings
from typing import Any, Dict, List

import joblib
import numpy as np
import pandas as pd

from app.config import get_settings
from app.ml import transformers  # noqa: F401  (makes IQRCapper importable for unpickling)
from app.schemas.features import FEATURE_COLUMNS, FEATURE_SPECS, KEY_TO_COLUMN

log = logging.getLogger("app.model")

_SPEC_BY_COL = {s["column"]: s for s in FEATURE_SPECS}


class ModelService:
    def __init__(self) -> None:
        self.pipeline = None
        self.meta: Dict[str, Any] = {}

    # ---- lifecycle --------------------------------------------------------------------------
    def load(self) -> None:
        s = get_settings()
        if not s.model_path.exists():
            raise RuntimeError(f"{s.model_path} not found. Run `python export_model.py` first.")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.pipeline = joblib.load(s.model_path)
        for w in caught:
            log.warning("while loading model.pkl: %s", w.message)    # e.g. scikit-learn version mismatch
        self.meta = json.loads(s.metadata_path.read_text())
        if self.meta["features"] != FEATURE_COLUMNS:
            raise RuntimeError("Feature order in model_metadata.json differs from the API schema")
        cap = self._cap_step()
        self._cap_lower = dict(zip(FEATURE_COLUMNS, cap.lower_))
        self._cap_upper = dict(zip(FEATURE_COLUMNS, cap.upper_))
        log.info("Model loaded: %s (%d features)", self.meta["model_name"], len(FEATURE_COLUMNS))

    def _cap_step(self):
        return self.pipeline.named_steps["preprocessor"].named_transformers_["num"].named_steps["outlier_cap"]

    @property
    def ready(self) -> bool:
        return self.pipeline is not None

    # ---- inference --------------------------------------------------------------------------
    def predict(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """`payload` uses API keys (co_gt, temperature, ...). Returns the raw prediction + honest context."""
        row = {KEY_TO_COLUMN[k]: (np.nan if v is None else float(v)) for k, v in payload.items()}
        X = pd.DataFrame([[row.get(c, np.nan) for c in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS)  # training order
        pred = float(self.pipeline.predict(X)[0])
        if not np.isfinite(pred):
            raise ValueError("Model produced a non-finite value")

        warnings_out: List[Dict[str, str]] = []
        capped, imputed = [], []
        ranges = self.meta["training_ranges"]
        for col in FEATURE_COLUMNS:
            label = _SPEC_BY_COL[col]["label"]
            v = row.get(col, np.nan)
            if np.isnan(v):
                imputed.append(label)
                continue
            lo, hi = ranges[col]["min"], ranges[col]["max"]
            if v < lo or v > hi:
                warnings_out.append({"feature": label,
                                     "message": f"{v:g} is outside the range seen in training ({lo:g} to {hi:g}); "
                                                f"the prediction is an extrapolation and may be less reliable."})
            if v < self._cap_lower[col] or v > self._cap_upper[col]:
                capped.append(label)
        if capped:
            warnings_out.append({"feature": ", ".join(capped),
                                 "message": "Beyond the pipeline's IQR limits; these values are clipped to the limits before prediction."})
        if pred < 0 or pred > 100:
            warnings_out.append({"feature": "Relative Humidity",
                                 "message": f"The raw model output ({pred:.1f} %) is outside the physical 0-100 % range, "
                                            f"which indicates unusual inputs. Treat it with caution."})

        m = self.meta["notebook_metrics_test"]
        return {
            "prediction": round(pred, 2),
            "model_name": self.meta["model_name"],
            "notebook_test_mae": m["mae"], "notebook_test_rmse": m["rmse"], "notebook_test_r2": m["r2_test"],
            "explanation": (
                f"The {self.meta['model_name']} model estimates relative humidity at {pred:.1f} % for the inputs "
                f"provided. On the notebook's held-out test data this model had a mean absolute error of "
                f"{m['mae']:.2f} percentage points (RMSE {m['rmse']:.2f}, R² {m['r2_test']:.3f}). "
                f"This is an average over the test set, not a confidence interval for this single prediction."),
            "warnings": warnings_out,
            "imputed_features": imputed,
            "capped_features": capped,
            "inputs_used": {c: (None if np.isnan(row.get(c, np.nan)) else row[c]) for c in FEATURE_COLUMNS},
        }


model_service = ModelService()
