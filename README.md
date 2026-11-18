# Notebook -> PKL -> private FastAPI -> Flutter app (Relative Humidity prediction)

```
notebook/original_notebook.ipynb   your executed notebook (unchanged)
backend/                           export_model.py, artifacts/model.pkl, FastAPI service, tests, Docker
mobile_app/                        Flutter app (login, dynamic form, "Check Prediction", result)
```

## 1. Analysis of the notebook
| Item | Finding |
|---|---|
| Dataset / task | UCI *Air Quality* (9,357 hourly rows). **Regression**: predict **RH** (relative humidity, %) |
| Target leakage guard | `AH` (absolute humidity) dropped on purpose - it is computed from T and RH |
| Features (13, in order) | CO(GT), PT08.S1(CO), C6H6(GT), PT08.S2(NMHC), NOx(GT), PT08.S3(NOx), NO2(GT), PT08.S4(NO2), PT08.S5(O3), T, Month, DayOfWeek, Hour (all numeric; Month/DayOfWeek/Hour derived from Date/Time) |
| Cleaning | -200 -> NaN; `NMHC(GT)` dropped (>40 % missing); 366 rows without RH dropped; no duplicates |
| Preprocessing (in the pipeline, fit on train only) | median imputation -> IQR capping (1.5x) -> StandardScaler |
| Models compared | Linear (R² 0.827), poly-2 (0.944), **poly-3 (0.966)**, poly-4 (0.941) |
| Final model | `Pipeline[ColumnTransformer -> PolynomialFeatures(3) -> LinearRegression]`, 559 expanded features |
| Notebook metrics (test) | MAE 2.3916 - RMSE 3.2442 - R² 0.9658 - 5-fold CV R² 0.9662 +/- 0.0020 |

## 2. What was done / verified
* `backend/artifacts/model.pkl` - the full inference pipeline (preprocessing + polynomial + regression), written by `backend/export_model.py`.
* The notebook has no saved model, so the pipeline was **rebuilt by executing the notebook's own code** and then checked
  against the notebook's printed results (intercept, all metrics, split sizes, first 10 predictions, top coefficients) -
  all identical; the export aborts if they are not. Details and the dataset caveat: `backend/README.md` section 2.
* 36 automated backend tests pass; a live `uvicorn` run was exercised over HTTP with real tokens (login -> predict -> 422 on bad input -> 401 without token).
* Reloaded `model.pkl` reproduces the in-memory model's predictions on all 1,799 test rows with zero difference.

## 3. What was NOT verified (please read)
* **The Flutter app has not been compiled or run** - no Flutter SDK was available in the build environment. It was written
  against the verified API and a contract test checks the JSON keys it reads, but expect to run `flutter analyze` and fix
  any small compile issue. "Mobile-to-backend works on a device" is therefore **not yet demonstrated**; follow
  `mobile_app/README.md` to run it (about 10 minutes) and treat the project as complete only after that works for you.
* Your original CSV was not in the upload; the dataset was reconstructed (see backend README). Metrics matching exactly is strong
  evidence, and `export_model.py --data` re-checks with your original file.
* Production HTTPS/Docker files are provided but were not deployed.

## 4. Quick start
```bash
cd backend && pip install -r requirements-dev.txt && cp .env.example .env   # set SECRET_KEY, ADMIN_PASSWORD
uvicorn main:app --host 0.0.0.0 --port 8000
cd ../mobile_app && flutter create . --project-name rh_predictor && flutter pub get
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```
Dataset licence: UCI Air Quality, CC BY 4.0 (De Vito et al., 2008).
