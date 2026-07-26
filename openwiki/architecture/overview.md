# Architecture overview

FastAPI Blog is a single FastAPI application that serves both browser pages and JSON APIs. The codebase is intentionally compact: `main.py` wires the app together, `routers/` contains API behavior, `models.py` defines SQLModel tables and schemas, and templates/static assets provide the browser UI.

## Runtime shape

`main.py` is the application entrypoint:

- Creates `app = FastAPI(lifespan=create_db_resource)`.
- Mounts static assets from `static/` at `/static`.
- Creates `Jinja2Templates(directory="templates")` for server-rendered pages.
- Includes `routers.users.router` at `/api/users` and `routers.posts.router` at `/api/posts`.
- Disposes the async database engine on shutdown in the lifespan context.

The app does **not** create tables at startup. Schema management is expected to happen through Alembic migrations before runtime.

## Request surfaces

### Browser pages

Page routes live in `main.py` and render templates:

- `/` and `/posts` render `templates/home.html` with the first page of posts.
- `/posts/{post_id}` renders `templates/post.html` for a post detail.
- `/users/{user_id}/posts` renders `templates/user_posts.html` for an author's posts.
- `/login`, `/register`, `/account`, `/forgot-password`, and `/reset-password` render their respective account/auth pages.

The server-rendered pages rely on JavaScript modules for interactive API calls:

- `static/js/auth.js` stores the bearer token in `localStorage`, caches `/api/users/me`, and handles logout.
- `static/js/utils.js` centralizes modal display, API error extraction, HTML escaping, and date formatting.
- `templates/layout.html` updates navbar state based on the current user and handles the global create-post modal.
- `templates/home.html` and `templates/user_posts.html` fetch more posts through API pagination.
- `templates/post.html` shows edit/delete controls only to the author, then calls the post API.
- `templates/account.html` calls profile, picture, password, logout, and account deletion APIs.

### JSON APIs

The API routers are mounted with `redirect_slashes=False`, so callers should use the exact paths shown here:

- `/api/users` — register a user.
- `/api/users/token` — log in and return a bearer JWT.
- `/api/users/me` — return the current authenticated user.
- `/api/users/forgot-password`, `/api/users/reset-password`, `/api/users/me/password` — password reset/change flows.
- `/api/users/{user_id}` — get/update/delete a user.
- `/api/users/{user_id}/picture` — upload/delete the user's profile picture.
- `/api/users/{user_id}/posts` — list a user's posts.
- `/api/posts` — list or create posts.
- `/api/posts/{post_id}` — get/update/delete a post.

See [Users/auth](../domain/users-auth.md) and [Posts/content](../domain/posts-content.md) for behavior and authorization rules.

## Database access

`database.py` creates an async SQLAlchemy engine from `settings.database_url` and exposes:

- `async_session`, an `async_sessionmaker` using `AsyncSession` and `expire_on_commit=False`.
- `get_db()`, a FastAPI dependency that yields one async session per request.

Routes use SQLModel/SQLAlchemy `select()` statements and usually eager-load post authors with `selectinload(models.Post.author)` before serializing `PostResponse` or rendering templates. This is important because response models include nested author data and templates render `post.author.image_path`.

## Settings and configuration

`config.py` defines a Pydantic Settings object loaded from environment variables and `.env` via `SettingsConfigDict(env_file=".env")`. Important settings include database URLs, JWT secret/algorithm/expiry, upload size, S3 bucket details, pagination size, password-reset expiry, SMTP settings, and `FRONTEND_URL`.

Do not read or document live `.env` values. Use setting names only.

Two database URLs are intentionally separate:

- `DATABASE_URL` (`settings.database_url`) is used by the async app runtime in `database.py`.
- `DATABASE_URL_DIRECT` (`settings.database_url_direct`) is inserted into Alembic config in `alembic/env.py`.

## Security and error handling

`main.py` adds security headers on every response:

- `X-Frame-Options: SAMEORIGIN`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin` unless already set
- `Strict-Transport-Security` for non-localhost requests

The `/reset-password` page overrides `Referrer-Policy` to `no-referrer` so reset tokens in the URL are less likely to leak through referrers.

Error handling is split by route surface:

- Paths starting with `/api` use FastAPI's standard JSON exception handlers.
- Browser routes render `templates/error.html` for HTTP and validation errors.

## Health check

`GET /health` executes `SELECT 1` through `database.get_db`. It returns `{"status": "healthy"}` when the database is reachable and raises HTTP 503 with `"Database unavailable"` otherwise.

Recent git history shows this endpoint was added just before Docker deployment work, so treat it as the deployment/orchestrator readiness check.

## Architectural watch points

- Local development uses Python 3.12 (`.python-version` and `pyproject.toml`), while the Dockerfile currently uses `python:3.14.4-slim-bookworm`. Reconcile this before assuming identical behavior across environments.
- Browser auth state depends on bearer tokens in `localStorage`; server routes still enforce authorization through `CurrentUser`, so do not rely on hidden UI controls as security.
- `models.UserBase.image_path` builds an AWS S3 public URL from bucket and region. If `S3_ENDPOINT_URL` is used for non-AWS S3-compatible storage, generated public URLs may need review.
- The app lifespan only disposes the DB engine. It does not warm connections, run migrations, or verify external S3/SMTP configuration.
