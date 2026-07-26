# Deployment and operations

This page summarizes how the app is configured, run, checked, and deployed. Evidence comes from `Dockerfile`, `.dockerignore`, `main.py`, `config.py`, `gcp_deploy.txt`, `vps_setup.txt`, and `.github/workflows/openwiki-update.yml`.

## Local run shape

The project uses `uv` and FastAPI CLI commands in deployment notes.

Typical local sequence:

```bash
uv sync
uv run alembic upgrade head
uv run fastapi run --host 0.0.0.0 --port 8000
```

Before running, provide environment variables for settings in `config.py`. At minimum, the app needs database URLs, a JWT secret, and S3 bucket configuration because `Settings` is instantiated at import time.

The browser app is available at `/`; the OpenAPI docs are available through FastAPI defaults unless disabled elsewhere; the deployment health check is `/health`.

## Health and readiness

`GET /health` in `main.py` executes `SELECT 1` through the normal database dependency.

- Success: `{"status": "healthy"}`.
- Database failure: HTTP 503 with `"Database unavailable"`.

Use this for container/orchestrator health checks when database connectivity is required.

## Docker image

`Dockerfile` is a two-stage build:

1. **Builder stage**
   - Base: `python:3.14.4-slim-bookworm`.
   - Copies `uv` from `ghcr.io/astral-sh/uv:0.11.6`.
   - Sets `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`, and `UV_PYTHON_DOWNLOADS=0`.
   - Copies `pyproject.toml` and `uv.lock` first for dependency caching.
   - Runs `uv sync --locked --no-install-project --no-dev`, then copies the app and runs `uv sync --locked --no-dev`.

2. **Production stage**
   - Base: `python:3.14.4-slim-bookworm`.
   - Creates and runs as non-root `appuser`.
   - Copies `/app` from the builder stage.
   - Sets `PATH=/app/.venv/bin:$PATH`, `PYTHONUNBUFFERED=1`, and `PORT=8080`.
   - Starts with:

     ```bash
     fastapi run --host 0.0.0.0 --port "$PORT" --proxy-headers --forwarded-allow-ips '*'
     ```

`.dockerignore` excludes `.git/`, tests, `.env`, database files, virtualenvs, caches, build artifacts, and common OS/editor noise.

Watch point: local project metadata targets Python 3.12+, while Docker uses Python 3.14.4. Align this before treating local and container results as equivalent.

## Cloud Run notes

`gcp_deploy.txt` records manual Google Cloud commands:

- Enable Cloud Run, Cloud Build, and Artifact Registry services.
- Create a Docker Artifact Registry repository in `asia-east2`.
- Build and tag the image with `gcloud builds submit`.
- Deploy to Cloud Run with `gcloud run deploy ... --allow-unauthenticated`.

The file contains concrete project/repository/image names from the author's environment. Treat it as a worked example that must be adapted for another project, not a portable script.

## VPS/systemd/nginx notes

`vps_setup.txt` is a longer runbook for deploying on a VPS. High-signal parts for this app:

- Copy project files to `/var/www/fastapi-blog/`.
- Lock down permissions, while allowing nginx to traverse/read static files.
- Run `uv sync` in the project directory.
- Create `.env` with database, secret key, mail, frontend, and S3 settings.
- Secure `.env` with `chmod 600`.
- Run `uv run alembic upgrade head`.
- Test manually with `uv run fastapi run --host 0.0.0.0 --port 8000`.
- Create a `fastapi-blog.service` systemd unit that runs FastAPI on `127.0.0.1:8000` with `--proxy-headers`.
- Put nginx in front of the app.
- Set `client_max_body_size 5M`, matching `settings.max_upload_size_bytes`.
- Use `journalctl -u fastapi-blog` for app logs and nginx logs for proxy issues.
- On code updates: `git pull`, `uv sync`, `uv run alembic upgrade head`, restart the service.

The runbook also includes security checklist items and TODOs for PostgreSQL backups and monitoring.

## Required environment variable names

Do not document actual secret values. Names from `config.py` are:

- `DATABASE_URL`
- `DATABASE_URL_DIRECT`
- `SECRET_KEY`
- `ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `MAX_UPLOAD_SIZE_BYTES`
- `S3_BUCKET_NAME`
- `S3_REGION`
- `S3_ACCESS_KEY_ID`
- `S3_SECRET_ACCESS_KEY`
- `S3_ENDPOINT_URL`
- `POSTS_PER_PAGE`
- `RESET_TOKEN_EXPIRE_MINUTES`
- `MAIL_SERVER`
- `MAIL_PORT`
- `MAIL_USERNAME`
- `MAIL_PASSWORD`
- `MAIL_FROM`
- `MAIL_USE_TLS`
- `FRONTEND_URL`

## Operational checks

After deployment or a config change:

1. Run migrations: `uv run alembic upgrade head`.
2. Start/restart the process.
3. Check `/health`.
4. Load `/` and verify static assets render.
5. Register/login with a non-production test account if appropriate.
6. Create a post and verify it appears in the feed.
7. Upload a small profile image if S3 configuration changed.
8. Use `check.s3.py` in a safe environment to verify bucket upload/delete permissions.
9. Trigger forgot-password only in an environment where SMTP is intentionally configured.

## OpenWiki documentation automation

`.github/workflows/openwiki-update.yml` defines a scheduled/manual GitHub Actions workflow:

- Checks out the repository.
- Sets up Node.js 22.
- Installs OpenWiki globally with npm.
- Runs `openwiki code --update --print`.
- Opens a pull request with changes under `openwiki/`.

The workflow uses secret names such as `OPENROUTER_API_KEY` and `LANGSMITH_API_KEY`; do not print or copy their values.

## Operations watch points

- `README.md` is empty, so operators should start from this wiki and the deployment text files.
- `vps_setup.txt` contains broad server-hardening instructions and example shell commands; adapt with care rather than pasting blindly into production.
- The app performs DB readiness checks but not S3/SMTP readiness checks at startup.
- Password reset and email flows depend on `FRONTEND_URL` matching the public origin.
- Browser auth uses `localStorage`; HTTPS is required in production to protect bearer tokens in transit.
