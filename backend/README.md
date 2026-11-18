# Backend - private FastAPI service

Serves the notebook's **Polynomial Regression (degree 3)** pipeline from `artifacts/model.pkl`.

## 1. Setup
```bash
cd backend
python -m venv .venv && source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env     # then edit: SECRET_KEY (random, >=32 chars), ADMIN_PASSWORD
python -c "import secrets;print(secrets.token_urlsafe(48))"   # paste as SECRET_KEY
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
Swagger UI: http://localhost:8000/docs (click **Authorize**, log in with the admin from `.env`).
`artifacts/model.pkl` is already included. Python/scikit-learn/numpy/pandas versions in `requirements.txt` match the
ones that created it - keep them, or re-run `python export_model.py`.

Users (no public sign-up):
```bash
python manage_users.py create alice          # prompts for password (min 10 chars)
python manage_users.py list | deactivate alice | passwd alice
```

## 2. How the model file was produced (`export_model.py`)
The executed notebook holds **no saved model object** and the CSV had been uploaded by hand to Colab, so the fitted
pipeline had to be rebuilt by running the notebook's own code on the dataset:

* Same cleaning (-200 -> NaN, Date/Time -> Month/DayOfWeek/Hour, drop `NMHC(GT)` (>40 % missing) and `AH`, drop rows
  with missing RH), same split (`test_size=0.2, random_state=42`), same pipeline, same `PolynomialFeatures(degree=3)` +
  `LinearRegression`. Nothing was tuned or replaced.
* **Model selection** - the notebook compared degrees 1-4 on the test set (R² 0.8274 / 0.9435 / **0.9658** / 0.9414);
  degree 3 is the notebook's own final choice.
* **Verification (automatic, blocks the export on mismatch)** against numbers printed in the executed notebook:
  intercept 44.7354, MAE 2.3916, MSE 10.5250, RMSE 3.2442, R² 0.9658 (test) / 0.9742 (train), 7192/1799 split,
  559 expanded features, the first 10 test predictions, and the three largest coefficients. All matched.
* The custom `IQRCapper` lives in `app/ml/transformers.py` (identical code) so the pickle can be loaded outside the notebook.

**Dataset note:** the original CSV file was not part of the upload. It was reconstructed from public mirrors of the UCI
*Air Quality* dataset (one mirror lost decimals; another was shuffled with different formatting; they were merged and
re-sorted chronologically and cross-checked). The result reproduces every statistic and metric printed in your notebook,
which is the evidence it equals your data. If you have your original `AirQualityUCI.csv`, run
`python export_model.py --data /path/to/AirQualityUCI.csv` - it will either confirm the same numbers or refuse to export.

## 3. API
Base: `/api/v1`. Everything except `/health` needs `Authorization: Bearer <access token>`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | none | liveness |
| POST | `/api/v1/auth/login` | none (form: username, password) | access + refresh tokens |
| POST | `/api/v1/auth/refresh` | refresh token | rotate tokens (one-time use) |
| POST | `/api/v1/auth/logout` | user | revoke tokens |
| GET | `/api/v1/auth/me` | user | current user |
| GET | `/api/v1/model/schema` | user | model info + the 13 input features (drives the mobile form) |
| POST | `/api/v1/predict` | user | prediction |
| POST/GET | `/api/v1/admin/users`, `POST .../{u}/deactivate` | admin | user management |

**Input fields (order = training order):** `co_gt`\*, `pt08_s1_co`, `c6h6_gt`, `pt08_s2_nmhc`, `nox_gt`\*, `pt08_s3_nox`,
`no2_gt`\*, `pt08_s4_no2`, `pt08_s5_o3`, `temperature`, `month` (1-12), `day_of_week` (0=Mon..6=Sun), `hour` (0-23).
\* optional - these had ~18 % missing values in training and the pipeline's median imputer handles them.
Unknown fields, NaN/Infinity, wrong types and out-of-range values return **422** with per-field messages.

**Output:** `prediction` (RH %, raw model output rounded to 2 dp), the notebook's test MAE/RMSE/R², an explanation, and
`warnings` (inputs outside the training range; raw output outside 0-100 %), `imputed_features`, `capped_features`.
There is **no probability/confidence score** because the model is a linear regression on polynomial features and does
not produce one; the API deliberately does not invent one.

## 4. Testing
```bash
pytest -q          # 36 tests
```
Covers: pickle loads & structure, feature order, API == direct pipeline, 25 reference predictions, auth
(missing/garbage/tampered/wrong-type token, wrong password, lockout 429, refresh rotation/reuse, logout, deactivation,
role 403), validation (10 invalid-input cases, NaN), extrapolation warnings, security headers, and the JSON contract the
Flutter models rely on.

Manual (curl):
```bash
B=http://localhost:8000
TOK=$(curl -s -X POST $B/api/v1/auth/login -d 'username=admin&password=YOUR_PASSWORD' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s -X POST $B/api/v1/predict -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d '{
 "co_gt":2.6,"pt08_s1_co":1360,"c6h6_gt":11.9,"pt08_s2_nmhc":1046,"nox_gt":166,"pt08_s3_nox":1056,
 "no2_gt":113,"pt08_s4_no2":1692,"pt08_s5_o3":1268,"temperature":13.6,"month":3,"day_of_week":2,"hour":18}'
# -> prediction 50.08 (the dataset's actual RH for that row is 48.9; the notebook's test MAE is 2.39)
curl -i -X POST $B/api/v1/predict -H 'Content-Type: application/json' -d '{}'      # -> 401
```
Postman: import `http://localhost:8000/openapi.json`, set the collection's Authorization to Bearer Token.

## 5. Security measures
bcrypt password hashes; short-lived JWT access tokens + rotating, revocable refresh tokens; user re-checked in the DB
on every request (deactivation is immediate); login lockout (5 failures/15 min per user+IP) and constant-time
handling of unknown users; role-based authorization for admin routes; secrets only from environment (app refuses to
start with a weak `SECRET_KEY`); strict input validation (`extra=forbid`); request bodies never logged; security
headers; HTTPS redirect + HSTS (`ENFORCE_HTTPS`); host allow-list; docs can be disabled; non-root container.
The mobile app contains **no secret** - only the server URL; each person logs in with their own account.

## 6. Production deployment
1. A server with Docker and a DNS record `api.example.com` pointing to it.
2. `.env` with: `SECRET_KEY` (new random), `ADMIN_USERNAME/ADMIN_PASSWORD` (first start only), `API_DOMAIN=api.example.com`,
   `ALLOWED_HOSTS=["api.example.com"]`.
3. `docker compose up -d --build` - Caddy obtains/renews a Let's Encrypt certificate automatically and proxies to the API
   (`ENVIRONMENT=production`, `ENFORCE_HTTPS=true`, docs off are set in `docker-compose.yml`).
4. Remove `ADMIN_PASSWORD` from `.env`, then `docker compose up -d`. Add users:
   `docker compose exec api python manage_users.py create alice`.
5. Back up the `api_data` volume (SQLite). Run a single API replica with SQLite (the login throttle is in-memory);
   for several replicas move users to PostgreSQL and the throttle to Redis.
6. Build the app with `--dart-define=API_BASE_URL=https://api.example.com`.
