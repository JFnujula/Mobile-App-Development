# Vercel private deployment

## Architecture

Vercel runs `api/index.py` as the FastAPI serverless function. The model is bundled as a
private deployment asset and is loaded by the backend only; it is not exposed by a route.
Local development continues to use SQLite, while Vercel uses PostgreSQL/Neon through
`DATABASE_URL`. This is required because a Vercel function's local filesystem is
ephemeral and cannot safely persist users or revoked tokens.

## Deploy

1. Push this repository to a private GitHub repository.
2. In Vercel, import the repository and set **Root Directory** to `backend`.
3. Keep the framework preset as **Other**. `backend/vercel.json` configures the Python
   serverless function and includes the model artifact.
4. Create a Neon or Vercel Postgres database and copy its pooled connection string.
5. Add these Vercel environment variables for **Production**:

   - `ENVIRONMENT=production`
   - `SECRET_KEY`: a new random value of at least 32 characters
   - `DATABASE_URL`: the PostgreSQL connection string
   - `ADMIN_USERNAME`: the first approved account
   - `ADMIN_PASSWORD`: a strong password, used only for the first initialization
   - `ENABLE_DOCS=false`
   - `ENFORCE_HTTPS=true`
   - `ALLOWED_HOSTS=["your-project.vercel.app"]`
   - `CORS_ORIGINS=[]`

6. Deploy, then call `https://your-project.vercel.app/health`. A successful response is
   `{"status":"ok"}`.
7. Log in once through the API, verify an authenticated `/api/v1/model/schema` request,
   and make a real `/api/v1/predict` request. Do not claim production completion until
   all three requests succeed.
8. Remove `ADMIN_PASSWORD` from Vercel after the first successful initialization and
   redeploy. Create later users with `DATABASE_URL` set locally:

   ```powershell
   $env:DATABASE_URL = "<same pooled connection string>"
   python manage_users.py create student
   ```

## Flutter build

Use the deployed URL when building the mobile client:

```powershell
flutter build apk --release `
  --dart-define=API_BASE_URL=https://your-project.vercel.app
```

The mobile app contains no database credentials or model file. Each approved user
authenticates with their own account; access and refresh tokens expire and logout
revokes refresh tokens.

## Verification checklist

- `GET /health` returns 200 without authentication.
- `POST /api/v1/auth/login` returns tokens for an approved account.
- Requests without a token to `/api/v1/model/schema` and `/api/v1/predict` return 401.
- An authenticated schema request returns the 13 model features.
- An authenticated prediction returns a numeric `prediction`.
- `GET /docs` is unavailable in production.
- The model is present only in the function bundle and cannot be downloaded as a
  static file.
- The Flutter release build uses the HTTPS Vercel URL.

The actual Vercel URL, dashboard environment variables, database credentials, and
production test responses must be filled in after deployment. They cannot be produced
locally without access to the Vercel and database accounts.
