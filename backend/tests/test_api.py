import time

import pytest

from tests.conftest import VALID, login

P = "/api/v1/predict"


# ---------- authentication / authorization ----------------------------------------------------
def test_health_is_public(client):
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("method,url", [("post", P), ("get", "/api/v1/model/schema"), ("get", "/api/v1/auth/me"),
                                        ("get", "/api/v1/admin/users")])
def test_endpoints_reject_missing_token(client, method, url):
    r = getattr(client, method)(url, **({"json": VALID} if method == "post" else {}))
    assert r.status_code == 401


def test_rejects_garbage_and_wrong_type_tokens(client):
    assert client.post(P, json=VALID, headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401
    refresh = login(client, "alice", "correct-horse-battery").json()["refresh_token"]
    # a refresh token must not work as an access token
    assert client.post(P, json=VALID, headers={"Authorization": f"Bearer {refresh}"}).status_code == 401


def test_tampered_token_rejected(client, user_headers):
    tok = user_headers["Authorization"].split()[1]
    bad = tok[:-4] + ("AAAA" if not tok.endswith("AAAA") else "BBBB")
    assert client.post(P, json=VALID, headers={"Authorization": f"Bearer {bad}"}).status_code == 401


def test_login_wrong_password_and_unknown_user(client):
    assert login(client, "alice", "nope-nope-nope").status_code == 401
    assert login(client, "ghost", "whatever-long-pw").status_code == 401


def test_normal_user_cannot_use_admin_endpoints(client, user_headers):
    assert client.get("/api/v1/admin/users", headers=user_headers).status_code == 403


def test_admin_creates_user_who_can_login_and_be_deactivated(client, admin_headers):
    r = client.post("/api/v1/admin/users", headers=admin_headers,
                    json={"username": "bob", "password": "bobs-long-password", "role": "user"})
    assert r.status_code == 201
    tok = login(client, "bob", "bobs-long-password").json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.post(P, json=VALID, headers=h).status_code == 200
    assert client.post("/api/v1/admin/users/bob/deactivate", headers=admin_headers).status_code == 204
    assert client.post(P, json=VALID, headers=h).status_code == 401           # immediate effect
    assert login(client, "bob", "bobs-long-password").status_code == 401


def test_refresh_rotation_and_logout(client):
    t = login(client, "alice", "correct-horse-battery").json()
    t2 = client.post("/api/v1/auth/refresh", json={"refresh_token": t["refresh_token"]})
    assert t2.status_code == 200
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": t["refresh_token"]}).status_code == 401  # reuse
    new = t2.json()
    h = {"Authorization": f"Bearer {new['access_token']}"}
    assert client.post("/api/v1/auth/logout", json={"refresh_token": new["refresh_token"]}, headers=h).status_code == 204
    assert client.post(P, json=VALID, headers=h).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": new["refresh_token"]}).status_code == 401


def test_login_lockout_after_repeated_failures(client):
    for _ in range(5):
        assert login(client, "lockme", "wrong-password-1").status_code == 401
    r = login(client, "lockme", "wrong-password-1")
    assert r.status_code == 429 and "Retry-After" in r.headers


# ---------- validation ------------------------------------------------------------------------
def test_valid_prediction_shape(client, user_headers):
    r = client.post(P, json=VALID, headers=user_headers)
    assert r.status_code == 200
    j = r.json()
    assert isinstance(j["prediction"], float) and j["unit"] == "%"
    assert j["notebook_test_mae"] == pytest.approx(2.3916) and j["notebook_test_r2"] == pytest.approx(0.9658)
    assert "confidence" not in j                     # LinearRegression has none; nothing is fabricated
    assert j["imputed_features"] == [] and len(j["inputs_used"]) == 13


def test_optional_features_can_be_omitted_and_are_reported(client, user_headers):
    body = {k: v for k, v in VALID.items() if k not in ("co_gt", "nox_gt", "no2_gt")}
    r = client.post(P, json=body, headers=user_headers)
    assert r.status_code == 200
    assert len(r.json()["imputed_features"]) == 3


@pytest.mark.parametrize("mutate", [
    lambda b: b.pop("temperature"),                        # required missing
    lambda b: b.pop("hour"),
    lambda b: b.update(temperature=999),                   # out of sanity range
    lambda b: b.update(month=13),
    lambda b: b.update(day_of_week=7),
    lambda b: b.update(hour=24),
    lambda b: b.update(month=3.5),                         # not an integer
    lambda b: b.update(c6h6_gt="abc"),
    lambda b: b.update(c6h6_gt=-1),
    lambda b: b.update(extra_field=1),                     # unknown fields rejected
])
def test_invalid_input_returns_422_with_field_errors(client, user_headers, mutate):
    body = dict(VALID); mutate(body)
    r = client.post(P, json=body, headers=user_headers)
    assert r.status_code == 422
    assert r.json()["detail"] == "Validation failed" and r.json()["errors"]


def test_nan_and_infinity_rejected(client, user_headers):
    raw = '{"co_gt": NaN}'
    r = client.post(P, content=raw, headers={**user_headers, "Content-Type": "application/json"})
    assert r.status_code == 422


def test_extrapolation_is_flagged_not_hidden(client, user_headers):
    r = client.post(P, json={**VALID, "temperature": 55}, headers=user_headers)   # training max was 44.6 C
    assert r.status_code == 200
    assert any("outside the range seen in training" in w["message"] for w in r.json()["warnings"])


def test_model_schema_drives_the_form(client, user_headers):
    j = client.get("/api/v1/model/schema", headers=user_headers).json()
    assert [f["column"] for f in j["features"]][:2] == ["CO(GT)", "PT08.S1(CO)"] and len(j["features"]) == 13
    assert all("training_range" in f for f in j["features"])
    assert {f["key"] for f in j["features"]} == set(VALID)


def test_security_headers(client):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["cache-control"] == "no-store"
