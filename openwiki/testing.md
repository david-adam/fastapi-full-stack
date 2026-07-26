# Testing guide

The test suite uses pytest, AnyIO, httpx ASGI transport, SQLModel metadata setup, PostgreSQL, and moto-backed S3. Evidence lives in `pyproject.toml`, `tests/conftest.py`, `tests/test_users.py`, and `tests/test_posts.py`.

## Dependencies

Runtime dependencies relevant to tests include FastAPI, httpx, SQLModel, psycopg, Pillow, boto3, and pwdlib. Dev dependencies in `pyproject.toml` are:

- `pytest`
- `moto[s3]`
- `pyrefly`

Run tests with:

```bash
uv run pytest
```

## Fixture architecture

`tests/conftest.py` does several important things before importing the app:

- Sets environment variables for `DATABASE_URL`, `S3_BUCKET_NAME`, `SECRET_KEY`, S3 credentials, and AWS defaults.
- Imports `main.app` after setting those variables, so `config.settings` has test values.
- Enables `pytest_plugins = ["anyio"]` and fixes the backend to `asyncio`.
- Creates a session-scoped async SQLAlchemy engine using `postgresql+psycopg://postgres:postgres@localhost/test_blog` and `NullPool`.
- Creates all SQLModel tables once for the test session and drops them at teardown.
- Gives each test an `AsyncSession` inside a transaction/savepoint pattern, then rolls back after the test.
- Overrides `database.get_db` so requests use the test session.
- Uses `httpx.AsyncClient` with `ASGITransport(app=app)` to call the app in process.
- Uses moto's `mock_aws()` to create a fake S3 bucket for profile-picture tests.
- Provides helpers: `create_test_user()`, `login_user()`, and `auth_header()`.

## Prerequisites and caveats

- A local PostgreSQL server/database matching `tests/conftest.py` is required unless you change the fixture URL.
- `config.Settings` requires both `DATABASE_URL` and `DATABASE_URL_DIRECT`; the fixture sets `DATABASE_URL` but not `DATABASE_URL_DIRECT`. If no local `.env` supplies it, clean test runs may need an explicit `DATABASE_URL_DIRECT` test value before imports.
- The fixture uses `SQLModel.metadata.create_all()` rather than Alembic migrations, so tests can pass even if migration files are stale.
- The moto bucket is created in region `us-east-1`, while some test environment region strings are set to `ap-southest-1` (spelling as in source). If S3 behavior changes, revisit this setup.
- Tests should not rely on real `.env`, real S3, or real SMTP credentials.

## Current user/auth coverage

`tests/test_users.py` covers:

- Registration validation when required fields are missing.
- Duplicate email rejection.
- Successful registration and response filtering of password fields.
- Profile picture upload, generated `.jpg` filename, S3 URL shape, and moto S3 object creation.
- Forgot-password scheduling of `send_password_reset_email()` with expected kwargs.

Not currently covered:

- Login failure/success beyond helper usage.
- `/api/users/me` behavior.
- Profile username/email update.
- Account deletion and cascade behavior.
- Delete profile picture.
- Password reset completion and expired token behavior.
- Change-password behavior.
- S3 upload/delete failure cases.

## Current posts coverage

`tests/test_posts.py` covers:

- Empty post list.
- Missing post 404.
- Authenticated post creation.
- Unauthorized post creation rejection.
- Owner partial update.
- Wrong-user update rejection.
- Pagination totals, `skip`, `limit`, and `has_more`.

Not currently covered:

- Delete post.
- Full `PUT` update.
- `GET /api/users/{user_id}/posts`.
- Browser route rendering.
- The `/health` endpoint.
- Alembic migration application.
- Future `likes` behavior.

## Where to add tests

- Add user/auth tests to `tests/test_users.py` when touching `routers/users.py`, `auth.py`, `image_utils.py`, `email_utils.py`, or account/auth templates.
- Add post/content tests to `tests/test_posts.py` when touching `routers/posts.py`, post-related `main.py` routes, post templates, pagination, or post schemas.
- Add fixture-level helpers to `tests/conftest.py` only when they are shared across multiple tests.
- If a change depends on migrations, consider adding a migration-specific check instead of relying only on `SQLModel.metadata.create_all()`.

## Suggested verification by change type

| Change type | Minimum checks |
| --- | --- |
| Router/API behavior | `uv run pytest tests/test_users.py` or `uv run pytest tests/test_posts.py` plus affected new tests. |
| SQLModel schema | Run targeted tests and inspect/apply Alembic migration against a disposable database. |
| Profile images/S3 | Run user tests with moto and manually verify `check.s3.py` only in a safe configured environment. |
| Email/password reset | Mock email sending in tests; avoid sending real emails from automated tests. |
| Templates/static JS | Add API tests for backing behavior; manually smoke-test browser flows because current tests do not render/interact with pages. |
| Docker/deployment | Build/run the image, apply migrations, and check `/health`. |

## Testing watch points for future agents

- Do not read `.env` to make tests pass. Set safe test environment variables in the test process or fixture.
- Keep authorization tests explicit: UI hiding is not a substitute for router-level 401/403 assertions.
- Use moto or mocks for S3 behavior; avoid real AWS calls in tests.
- Use `AsyncClient`/`ASGITransport` patterns already present instead of adding separate live-server tests unless the change requires network-level behavior.
