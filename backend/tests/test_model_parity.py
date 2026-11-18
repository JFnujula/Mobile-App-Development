"""The served model must give the same numbers as the model trained in the notebook."""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from app.schemas.features import FEATURE_COLUMNS, FEATURE_SPECS
from tests.conftest import VALID

ART = Path(__file__).resolve().parent.parent / "artifacts"
KEY_BY_COL = {s["column"]: s["key"] for s in FEATURE_SPECS}


def test_pickle_loads_and_is_the_full_pipeline():
    p = joblib.load(ART / "model.pkl")
    assert [n for n, _ in p.steps] == ["preprocessor", "poly", "model"]
    assert p.named_steps["poly"].degree == 3
    assert p.named_steps["model"].intercept_ == pytest.approx(44.7354, abs=5e-5)     # printed in the notebook
    assert p[:-1].transform(pd.DataFrame([[0.0] * 13], columns=FEATURE_COLUMNS)).shape[1] == 559


def test_feature_order_matches_notebook():
    assert FEATURE_COLUMNS == ['CO(GT)', 'PT08.S1(CO)', 'C6H6(GT)', 'PT08.S2(NMHC)', 'NOx(GT)', 'PT08.S3(NOx)',
                               'NO2(GT)', 'PT08.S4(NO2)', 'PT08.S5(O3)', 'T', 'Month', 'DayOfWeek', 'Hour']


def test_api_matches_exported_reference_predictions(client, user_headers):
    ref = json.loads((ART / "reference_predictions.json").read_text())
    for case in ref["cases"]:
        body = {KEY_BY_COL[c]: v for c, v in case["input"].items() if v is not None}   # null -> omitted
        r = client.post("/api/v1/predict", json=body, headers=user_headers)
        assert r.status_code == 200, (body, r.text)
        assert r.json()["prediction"] == pytest.approx(case["expected"], abs=0.006)    # API rounds to 2 dp


def test_api_equals_direct_pipeline_call(client, user_headers):
    p = joblib.load(ART / "model.pkl")
    X = pd.DataFrame([[VALID[KEY_BY_COL[c]] for c in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS)
    expected = float(p.predict(X)[0])
    got = client.post("/api/v1/predict", json=VALID, headers=user_headers).json()["prediction"]
    assert got == pytest.approx(expected, abs=0.006)
    assert 40 < got < 58          # first dataset row had RH = 48.9 %; the notebook's model is accurate to ~2.4 pp


def test_not_a_constant_function(client, user_headers):
    a = client.post("/api/v1/predict", json=VALID, headers=user_headers).json()["prediction"]
    b = client.post("/api/v1/predict", json={**VALID, "temperature": 30.0}, headers=user_headers).json()["prediction"]
    assert abs(a - b) > 1
