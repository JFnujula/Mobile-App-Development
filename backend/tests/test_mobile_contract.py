"""Every JSON key read by the Flutter models (mobile_app/lib/models/*.dart) must exist in the real API responses."""
from tests.conftest import VALID

SPEC_KEYS = {"key", "column", "label", "unit", "type", "required", "min", "max", "help", "training_range"}
RESULT_KEYS = {"prediction", "target_label", "unit", "model_name", "notebook_test_mae", "notebook_test_rmse",
               "notebook_test_r2", "explanation", "warnings", "imputed_features"}


def test_schema_contract(client, user_headers):
    j = client.get("/api/v1/model/schema", headers=user_headers).json()
    assert {"model_name", "target", "notebook_metrics_test", "features"} <= set(j)
    assert {"label", "unit"} <= set(j["target"]) and {"mae", "rmse", "r2_test"} <= set(j["notebook_metrics_test"])
    for f in j["features"]:
        assert SPEC_KEYS <= set(f), f
        assert {"min", "max", "median"} <= set(f["training_range"])
        if f["type"] == "choice":
            assert f["options"] and all({"value", "label"} <= set(o) for o in f["options"])


def test_result_contract(client, user_headers):
    j = client.post("/api/v1/predict", json=VALID, headers=user_headers).json()
    assert RESULT_KEYS <= set(j)


def test_validation_error_contract(client, user_headers):
    j = client.post("/api/v1/predict", json={**VALID, "hour": 99}, headers=user_headers).json()
    assert j["errors"][0]["field"] == "hour" and isinstance(j["errors"][0]["message"], str)
