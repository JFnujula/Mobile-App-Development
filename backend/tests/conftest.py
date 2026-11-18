import os
import tempfile

import pytest

_TMP = tempfile.mkdtemp()
os.environ.update({
    "SECRET_KEY": "test-only-secret-key-0123456789-abcdefghijklmnop",
    "DATABASE_PATH": os.path.join(_TMP, "test.db"),
    "ENVIRONMENT": "development",
    "LOGIN_MAX_ATTEMPTS": "5",
})

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import user_service  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:                 # runs lifespan: init_db + model.pkl load
        user_service.create_user("alice", "correct-horse-battery", "user")
        user_service.create_user("boss", "another-long-password", "admin")
        yield c


def login(client, username, password):
    return client.post("/api/v1/auth/login", data={"username": username, "password": password})


@pytest.fixture()
def user_headers(client):
    r = login(client, "alice", "correct-horse-battery")
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def admin_headers(client):
    r = login(client, "boss", "another-long-password")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# A realistic input (values taken from the first row of the dataset; RH there was 48.9 %)
VALID = {"co_gt": 2.6, "pt08_s1_co": 1360, "c6h6_gt": 11.9, "pt08_s2_nmhc": 1046, "nox_gt": 166,
         "pt08_s3_nox": 1056, "no2_gt": 113, "pt08_s4_no2": 1692, "pt08_s5_o3": 1268, "temperature": 13.6,
         "month": 3, "day_of_week": 2, "hour": 18}
