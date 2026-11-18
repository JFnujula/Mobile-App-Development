#!/usr/bin/env python
"""
export_model.py - rebuilds the notebook's final model and serialises it to `artifacts/model.pkl`.

WHY THIS SCRIPT EXISTS
----------------------
The uploaded notebook (notebook/original_notebook.ipynb) was executed in Colab. It does not
contain the fitted model object (no pickle was saved) and the dataset was uploaded to Colab
by hand. So the trained pipeline has to be re-created by running the notebook's own code:

  * Sections 3, 8, 9, 10, 11 are reproduced below with identical logic and parameters
    (same cleaning, same split: test_size=0.2, random_state=42, same pipeline,
    PolynomialFeatures(degree=3, include_bias=False) + LinearRegression).
  * Nothing is tuned or changed. LinearRegression is deterministic, so the same data and the
    same split give the same coefficients.
  * Afterwards the script VERIFIES the rebuilt model against numbers that were printed in the
    executed notebook (intercept, MAE, MSE, RMSE, R2, first 10 test predictions, top-3
    coefficients). If any of them differs, the export aborts and no model.pkl is written.

Model selection (notebook Section 14 "Compare Linear vs Polynomial"): the notebook compared
degrees 1-4 on the test set and picked Polynomial Regression degree 3 (best test R2 = 0.9658).
`MODEL_NAME` / `POLY_DEGREE` in the notebook's config cell are set to exactly that.

USAGE
-----
    python export_model.py                       # uses data/AirQualityUCI.csv
    python export_model.py --data path/to.csv    # your own copy of the original UCI csv

Outputs (in ./artifacts):
    model.pkl                 full inference pipeline (impute -> IQR cap -> scale -> poly -> linreg)
    model_metadata.json       feature order/ranges, notebook metrics, versions
    reference_predictions.json  inputs + expected outputs used by tests/test_model_parity.py
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

from app.ml.transformers import IQRCapper

# ---- Notebook Section 2 configuration (unchanged) -------------------------------------------
TARGET_COLUMN = "RH"
DROP_COLUMNS = ["AH"]
MISSING_MARKERS = [-200]
MAX_MISSING_PCT = 40
DATE_COL, TIME_COL = "Date", "Time"
POLY_DEGREE = 3
TEST_SIZE, RANDOM_STATE = 0.2, 42

# ---- Values printed in the executed notebook (used only to VERIFY the rebuild) ---------------
NOTEBOOK_REFERENCE = {
    "intercept": 44.7354,
    "mae": 2.3916, "mse": 10.5250, "rmse": 3.2442, "r2_test": 0.9658, "r2_train": 0.9742,
    "n_train": 7192, "n_test": 1799, "n_model_features": 559,
    "first10_actual": [49.8, 46.4, 70.1, 37.9, 55.8, 44.9, 45.6, 52.6, 38.7, 40.1],
    "first10_predicted": [45.149, 43.851, 64.793, 37.253, 50.168, 41.390, 46.031, 55.348, 47.416, 43.095],
    "top3_coefs": {
        "num__C6H6(GT) num__PT08.S2(NMHC)^2": 60.269574,
        "num__C6H6(GT)^2 num__PT08.S2(NMHC)": -54.842283,
        "num__PT08.S2(NMHC)": -42.493917,
    },
}

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "artifacts")


def load_and_clean(path: str) -> pd.DataFrame:
    """Notebook Section 3 (load + generic cleaning), same logic."""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        header = f.readline()
    sep = max([",", ";", "\t", "|"], key=header.count)
    df = pd.read_csv(path, sep=sep, low_memory=False)
    for col in df.select_dtypes(exclude="number").columns:
        s = df[col].dropna().astype(str)
        if len(s) and s.str.fullmatch(r"-?\d+,\d+").mean() > 0.5:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    df.columns = df.columns.astype(str).str.strip()
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
    df = df.dropna(how="all").reset_index(drop=True)

    num_c = df.select_dtypes(include="number").columns
    df[num_c] = df[num_c].replace(MISSING_MARKERS, np.nan)

    d = pd.to_datetime(df[DATE_COL], dayfirst=True, errors="coerce")
    df["Month"], df["DayOfWeek"] = d.dt.month, d.dt.dayofweek
    df = df.drop(columns=[DATE_COL])
    df["Hour"] = pd.to_numeric(df[TIME_COL].astype(str).str.extract(r"^(\d{1,2})")[0], errors="coerce")
    df = df.drop(columns=[TIME_COL])

    too_missing = [c for c in df.columns if c != TARGET_COLUMN and df[c].isnull().mean() * 100 > MAX_MISSING_PCT]
    df = df.drop(columns=too_missing)
    df = df.drop(columns=[c for c in DROP_COLUMNS if c in df.columns])
    return df


def build_pipeline(num_features: list[str]) -> Pipeline:
    """Notebook Sections 10 + 11: preprocessing -> PolynomialFeatures(3) -> LinearRegression."""
    num_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("outlier_cap", IQRCapper(factor=1.5)),
        ("scaler", StandardScaler()),
    ])
    preprocessor = ColumnTransformer([("num", num_pipeline, num_features)])
    return Pipeline([
        ("preprocessor", clone(preprocessor)),
        ("poly", PolynomialFeatures(degree=POLY_DEGREE, include_bias=False)),
        ("model", LinearRegression()),
    ])


def verify(model, X_train, X_test, y_train, y_test, metrics) -> list[str]:
    ref, problems = NOTEBOOK_REFERENCE, []

    def close(name, got, want, tol):
        if abs(got - want) > tol:
            problems.append(f"{name}: rebuilt={got:.6f} notebook={want:.6f}")

    close("intercept", float(model.named_steps["model"].intercept_), ref["intercept"], 5e-5)
    for k in ("mae", "mse", "rmse", "r2_test", "r2_train"):
        close(k, metrics[k], ref[k], 5e-5)
    if len(X_train) != ref["n_train"] or len(X_test) != ref["n_test"]:
        problems.append(f"split sizes {len(X_train)}/{len(X_test)} != {ref['n_train']}/{ref['n_test']}")
    n_feat = model[:-1].transform(X_train.head(1)).shape[1]
    if n_feat != ref["n_model_features"]:
        problems.append(f"n features after expansion {n_feat} != {ref['n_model_features']}")
    pred10 = np.round(model.predict(X_test)[:10], 3)
    if not np.allclose(y_test.values[:10], ref["first10_actual"]):
        problems.append("first 10 actual test values differ (different split/data)")
    if not np.allclose(pred10, ref["first10_predicted"], atol=1.5e-3):
        problems.append(f"first 10 predictions differ: {pred10.tolist()}")
    coefs = pd.Series(model.named_steps["model"].coef_, index=model[:-1].get_feature_names_out())
    for name, want in ref["top3_coefs"].items():
        close(f"coef[{name}]", float(coefs[name]), want, 5e-6)
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(HERE, "data", "AirQualityUCI.csv"))
    ap.add_argument("--skip-verify", action="store_true", help="NOT recommended")
    args = ap.parse_args()

    df = load_and_clean(args.data)
    df = df.dropna(subset=[TARGET_COLUMN]).reset_index(drop=True)
    df = df.drop_duplicates().reset_index(drop=True)          # notebook Section 6 (0 duplicates found)
    X, y = df.drop(columns=[TARGET_COLUMN]), df[TARGET_COLUMN]
    features = X.columns.tolist()                              # ORIGINAL FEATURE ORDER
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE)

    model = build_pipeline(features)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    metrics = {
        "mae": float(mean_absolute_error(y_test, y_pred)), "mse": float(mse), "rmse": float(np.sqrt(mse)),
        "r2_test": float(r2_score(y_test, y_pred)),
        "r2_train": float(r2_score(y_train, model.predict(X_train))),
    }
    print("Rebuilt model metrics:", {k: round(v, 4) for k, v in metrics.items()})

    problems = verify(model, X_train, X_test, y_train, y_test, metrics)
    if problems and not args.skip_verify:
        print("\nVERIFICATION FAILED - model.pkl NOT written:")
        for p in problems:
            print("  -", p)
        print("Use the original, unmodified AirQualityUCI.csv (UCI Air Quality dataset).")
        return 1
    print("Verification against executed notebook outputs: " + ("PASSED" if not problems else "SKIPPED"))

    os.makedirs(OUT_DIR, exist_ok=True)
    joblib.dump(model, os.path.join(OUT_DIR, "model.pkl"), compress=3)

    # Training-data ranges (post-cleaning, before capping) are exposed to the API/mobile form.
    stats = X_train.describe().T
    meta = {
        "model_name": "Polynomial Regression (degree 3)",
        "target": {"name": TARGET_COLUMN, "label": "Relative Humidity", "unit": "%"},
        "features": features,
        "training_ranges": {c: {"min": float(stats.loc[c, "min"]), "max": float(stats.loc[c, "max"]),
                                "median": float(X_train[c].median()),
                                "missing_pct_in_training": round(float(X_train[c].isnull().mean() * 100), 2)}
                            for c in features},
        "notebook_metrics_test": {k: round(metrics[k], 4) for k in ("mae", "rmse", "r2_test")},
        "cv_r2_5fold": {"mean": 0.9662, "std": 0.0020},
        "n_train": int(len(X_train)), "n_test": int(len(X_test)),
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "versions": {"python": platform.python_version(), "scikit-learn": sklearn.__version__,
                     "numpy": np.__version__, "pandas": pd.__version__, "joblib": joblib.__version__},
    }
    with open(os.path.join(OUT_DIR, "model_metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)

    # Reference cases for parity tests: 25 real test rows (NaN kept as null) + in-memory predictions.
    ref_rows = X_test.head(25)
    ref = {"features": features,
           "cases": [{"input": {k: (None if pd.isna(v) else float(v)) for k, v in r.items()},
                      "expected": float(p)} for (_, r), p in zip(ref_rows.iterrows(), model.predict(ref_rows))]}
    with open(os.path.join(OUT_DIR, "reference_predictions.json"), "w") as f:
        json.dump(ref, f, indent=2)

    # Round-trip check: reload from disk and compare to the in-memory model on the whole test set.
    reloaded = joblib.load(os.path.join(OUT_DIR, "model.pkl"))
    diff = float(np.max(np.abs(reloaded.predict(X_test) - y_pred)))
    print(f"Reloaded model.pkl max |difference| vs in-memory model on {len(X_test)} test rows: {diff:.2e}")
    assert diff < 1e-9
    print("Saved:", os.listdir(OUT_DIR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
