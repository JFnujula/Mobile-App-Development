# RH Predictor - Flutter app

Mobile client for the private FastAPI backend (`../backend`).

**Why Flutter?** You did not specify a framework, so Flutter was chosen: one code base for Android and iOS,
native performance, built-in Material form widgets/validators, and `flutter_secure_storage` for Keystore/Keychain
token storage.

> **Status:** this code was written to match the verified backend API, but it was **not compiled or run** in the
> environment where the project was built (no Flutter SDK available there). Run `flutter analyze` and `flutter test`
> first; the steps below get you to a running app.

## Setup
```bash
cd mobile_app
flutter create . --project-name rh_predictor --org com.example   # generates android/ ios/ (keeps lib/ and pubspec.yaml)
flutter pub get
flutter analyze && flutter test
```

**Android only - add the INTERNET permission** (release builds need it) to
`android/app/src/main/AndroidManifest.xml`, inside `<manifest>` and above `<application>`:
```xml
<uses-permission android:name="android.permission.INTERNET"/>
```
`flutter_secure_storage` v9 needs `minSdkVersion 23`: in `android/app/build.gradle(.kts)` set `minSdk = 23`.

## Run against your backend
```bash
# Android emulator -> backend on your computer (10.0.2.2 is the emulator's alias for your PC)
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000

# Real phone on the same Wi-Fi: use your PC's LAN IP, e.g. http://192.168.1.20:8000
# (start uvicorn with --host 0.0.0.0). Plain http:// is only for development.
```
Android blocks plain-HTTP by default for release builds, and iOS blocks it via ATS. For development on Android
debug builds add `android:usesCleartextTraffic="true"` to `<application>`; **never ship that** - production must use HTTPS:
```bash
flutter build apk --release --dart-define=API_BASE_URL=https://api.example.com
```

## App flow
1. Login (username + password) -> tokens saved in secure storage.
2. The app downloads `/api/v1/model/schema` and **generates the form from it** (13 fields, units, ranges,
   required/optional, dropdown options for month / day / hour).
3. **Check Prediction** validates the form, shows a progress indicator, sends the authenticated request, and shows the real
   model output with the notebook's test MAE/RMSE/R² and any warnings.
4. Expired access tokens are refreshed automatically; if the refresh token is invalid the app returns to Login.
5. Network failures, timeouts, 401/422/429/5xx are mapped to readable messages.

## Structure
```
lib/main.dart                 app + auth gate
lib/config.dart               API_BASE_URL (--dart-define)
lib/models/                   FeatureSpec/ModelSchema, PredictionResult
lib/services/                 ApiClient (auth, refresh, errors), TokenStore (secure storage)
lib/screens/                  login, predict (dynamic form), result
lib/widgets/feature_field.dart  number / dropdown control + validators built from a FeatureSpec
```
