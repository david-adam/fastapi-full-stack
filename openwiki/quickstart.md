# FastAPI Blog OpenWiki quickstart

This OpenWiki documents the FastAPI Blog repository: a small full-stack FastAPI application with server-rendered Jinja pages, JSON APIs, PostgreSQL persistence, JWT authentication, password reset email, S3-backed profile pictures, and deployment notes for Docker/Cloud Run and a VPS.

The repository `README.md` is currently empty, so this wiki is the practical onboarding map for humans and future agents.

## Start here

- [Architecture overview](architecture/overview.md) — how requests flow through `main.py`, routers, templates, static JavaScript, settings, and the async database layer.
- [Users, authentication, and profile images](domain/users-auth.md) — registration, login, current-user lookup, password reset, account management, and S3 profile-picture behavior.
- [Posts, content, and pagination](domain/posts-content.md) — blog post APIs, ownership rules, list/detail pages, author pages, and demo content.
- [Data and storage](data-storage.md) — SQLModel models, PostgreSQL/Alembic migrations, S3 object layout, seed data, and configuration.
- [Deployment and operations](operations/deployment.md) — local run shape, Docker image, Cloud Run/VPS notes, health checks, environment variables, and OpenWiki automation.
- [Testing guide](testing.md) — pytest fixtures, covered scenarios, prerequisites, and gaps to close when changing behavior.

## What the app does

FastAPI Blog exposes two surfaces from the same application:

1. **Browser pages** rendered from `templates/` by route handlers in `main.py`.
2. **JSON APIs** mounted under `/api/users` and `/api/posts` by `routers/users.py` and `routers/posts.py`.

Core product flows:

- Visitors can view recent blog posts on `/` or `/posts`, open a post detail page, and view an author's posts.
- Users can register, log in with email/password, and store a bearer JWT in browser `localStorage`.
- Authenticated users can create posts, edit/delete only their own posts, update profile details, change passwords, and manage profile images.
- Forgot-password requests create a hashed reset-token record and send reset instructions through FastAPI background tasks and SMTP.
- Profile images are processed into 300x300 JPEGs and uploaded under `profile_pics/` in an S3 bucket; the default image is served from `/static/profile_pics/default.jpg`.

## Source map

| Area | Start with | Notes |
| --- | --- | --- |
| App entrypoint | `main.py` | Creates `FastAPI`, mounts `/static`, registers routers, renders HTML pages, adds security headers, exposes `/health`, and separates browser/API error handling. |
| API routers | `routers/users.py`, `routers/posts.py` | User/account/auth flows and post CRUD/pagination. Both routers are mounted with `redirect_slashes=False`. |
| Models and schemas | `models.py` | SQLModel tables and request/response schemas for users, posts, tokens, pagination, and password reset. |
| Auth helpers | `auth.py` | Password hashing, JWT creation/verification, reset-token hashing, and `CurrentUser` dependency. |
| Database | `database.py`, `alembic/` | Async SQLAlchemy engine/session and Alembic migrations driven by SQLModel metadata. |
| Templates and browser JS | `templates/`, `static/js/auth.js`, `static/js/utils.js` | Bootstrap/Jinja pages plus JavaScript fetch calls to the JSON APIs. |
| Image/email integrations | `image_utils.py`, `email_utils.py` | S3 client and image processing; SMTP email composition using the password-reset template. |
| Seed/demo data | `populate_db.py`, `populate_images/` | In-process ASGI client clears existing data, creates demo users/posts, uploads profile images, and adjusts dates. |
| Tests | `tests/conftest.py`, `tests/test_users.py`, `tests/test_posts.py` | Async httpx tests with dependency overrides, PostgreSQL test DB, and moto-backed S3. |
| Deployment | `Dockerfile`, `.dockerignore`, `gcp_deploy.txt`, `vps_setup.txt` | Docker/Cloud Run notes and a longer VPS/systemd/nginx setup guide. |
| Documentation automation | `.github/workflows/openwiki-update.yml` | Scheduled/manual workflow that runs OpenWiki and opens a docs PR. This file is currently present in the working tree. |

## Local development outline

The project uses `uv` and declares Python `>=3.12` in `pyproject.toml`; `.python-version` is `3.12`.

1. Install dependencies:

   ```bash
   uv sync
   ```

2. Create local configuration outside version control. Do **not** commit `.env`; it is ignored. Required or commonly used setting names are defined in `config.py`:

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
   - `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM`, `MAIL_USE_TLS`
   - `FRONTEND_URL`

3. Apply database migrations:

   ```bash
   uv run alembic upgrade head
   ```

   `alembic/env.py` reads `settings.database_url_direct`, while the app runtime in `database.py` uses `settings.database_url`.

4. Run the app. Deployment notes use the FastAPI CLI:

   ```bash
   uv run fastapi run --host 0.0.0.0 --port 8000
   ```

5. Check liveness and database connectivity:

   ```bash
   curl http://localhost:8000/health
   ```

6. Run tests when a local PostgreSQL test database is available:

   ```bash
   uv run pytest
   ```

   See [Testing guide](testing.md) before relying on this in a clean environment; `tests/conftest.py` hard-codes a PostgreSQL URL and currently sets only some required settings.

## Change-oriented guidance

- **Adding or changing API behavior:** start in the relevant router, then update `models.py` schemas, affected templates/JS, and tests. Keep server-side authorization checks even if the UI hides controls.
- **Changing persistence:** update `models.py`, generate/review Alembic migrations, and make sure tests still create the right schema or run migrations.
- **Changing auth or profile images:** read [Users, authentication, and profile images](domain/users-auth.md) and [Data and storage](data-storage.md); these flows cross routers, models, browser JS, S3, and tests.
- **Changing deployment:** reconcile local Python 3.12 with the Dockerfile's Python 3.14.4 base image before assuming parity.
- **Handling secrets:** never read, print, or copy live `.env` values. Document setting names and safe setup steps only.

## Known watch points from the initial pass

- `README.md` has no onboarding content.
- The working tree already had local changes before this OpenWiki run: `.gitignore`, `pyproject.toml`, `uv.lock`, `.DS_Store`, plus untracked agent/OpenWiki-related files. Source code was not modified by this documentation run.
- `email_utils.py` renders password-reset email text with `settings.access_token_expire_minutes`, while reset-token records use `settings.reset_token_expire_minutes` in `routers/users.py`.
- `models.Post.likes` exists and Alembic added a `posts.likes` column, but `PostResponse` and post APIs do not expose or mutate likes yet.
- `alembic/versions/1d67f41aa6dc_add_likes_to_posts.py` is a no-op follow-up migration after the actual likes-column migration.
- `tests/conftest.py` sets `DATABASE_URL` but not `DATABASE_URL_DIRECT`, even though `Settings` requires both. A local `.env` may hide this; clean CI may need an explicit test value.
