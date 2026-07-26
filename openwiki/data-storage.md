# Data and storage

FastAPI Blog stores relational data in PostgreSQL through SQLModel/SQLAlchemy and stores uploaded profile pictures in S3. This page explains the persistence model, migrations, seed data, and storage-related change checks.

## Settings that drive storage

`config.py` defines the storage-related settings:

- `DATABASE_URL` / `settings.database_url` — async app runtime URL used by `database.py`.
- `DATABASE_URL_DIRECT` / `settings.database_url_direct` — migration URL inserted into Alembic config by `alembic/env.py`.
- `S3_BUCKET_NAME`
- `S3_REGION`
- `S3_ACCESS_KEY_ID`
- `S3_SECRET_ACCESS_KEY`
- `S3_ENDPOINT_URL`
- `MAX_UPLOAD_SIZE_BYTES`
- `POSTS_PER_PAGE`

Do not read live `.env` values. Use these names when describing configuration.

## Relational model

`models.py` is the canonical model file.

Tables:

### `users`

Important columns:

- `id` primary key, indexed.
- `username` unique, non-null, max length 50.
- `email` unique, non-null, max length 120.
- `password_hash` non-null, max length 200.
- `image_file` optional, max length 200.

Relationships:

- `posts` back-populates `Post.author` and cascades delete-orphan.
- `reset_tokens` back-populates `PasswordResetToken.user` and cascades delete-orphan.

### `posts`

Important columns:

- `id` primary key.
- `title` indexed, length 1-100.
- `content` non-empty string.
- `date_posted` timezone-aware datetime with UTC default factory.
- `user_id` foreign key to `users.id`, indexed.
- `likes` integer with Python default 0 and server default 0.

### `password_reset_tokens`

Important columns:

- `id` primary key, indexed.
- `user_id` foreign key to `users.id`.
- `token_hash` unique SHA-256 hash of the raw reset token.
- `expires_at` datetime.
- `created_at` timezone-aware datetime defaulting to now.

## Database runtime

`database.py` creates:

- `engine = create_async_engine(settings.database_url)`
- `async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)`
- `get_db()`, a request dependency that yields an async session

`main.py` disposes this engine during application shutdown.

## Alembic migrations

Alembic is configured in `alembic.ini` and `alembic/env.py`.

Key details:

- `alembic/env.py` imports `models` so SQLModel metadata includes the app tables.
- `target_metadata = SQLModel.metadata` enables autogenerate against SQLModel definitions.
- `settings.database_url_direct` is written into Alembic's `sqlalchemy.url`.
- Migrations use async engine setup through `async_engine_from_config`.

Current migration chain:

1. `alembic/versions/ec4400fb08cf_initial_schema.py` — creates `users`, `password_reset_tokens`, and `posts` tables plus indexes/constraints.
2. `alembic/versions/3e5f566f2c0e_add_likes_column_to_posts.py` — adds non-null `posts.likes` with server default 0.
3. `alembic/versions/1d67f41aa6dc_add_likes_to_posts.py` — no-op migration following the actual likes-column migration.

Operational notes:

- Run migrations before app startup: `uv run alembic upgrade head`.
- When changing models, review generated migrations carefully; do not assume autogenerate captures every intended constraint or data migration.
- Tests currently create/drop `SQLModel.metadata` directly rather than running Alembic migrations, so migration correctness needs separate review.

## S3 profile image storage

`image_utils.py` owns image processing and object storage.

Object layout:

- Key prefix: `profile_pics/`
- Filename: random UUID hex plus `.jpg`
- Image format: JPEG
- Size: 300x300 crop via `ImageOps.fit`
- Upload content type: `image/jpeg`

S3 client construction uses:

- `settings.s3_region`
- optional `settings.s3_access_key_id`
- optional `settings.s3_secret_access_key`
- optional `settings.s3_endpoint_url`

`models.UserBase.image_path` computes display URLs as:

```text
https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/profile_pics/{image_file}
```

If no `image_file` exists, it returns `/static/profile_pics/default.jpg`.

`check.s3.py` is a small operational script that uploads and deletes `profile_pics/test.txt` to verify bucket permissions. It prints bucket and region names, but should not print secret values.

## Seed/demo data

`populate_db.py` is a destructive development/demo seed script. It clears S3 images and database tables, then uses the in-process FastAPI app with `httpx.ASGITransport` to create users, upload profile pictures, create posts, and update post dates.

Important behaviors:

- It calls real API routes, so it exercises validation/auth flows rather than inserting rows directly.
- It reads images from `populate_images/`.
- It deletes existing reset tokens, posts, and users.
- It deletes existing S3 objects for users with `image_file` values.

Never run it against production data unless the explicit goal is to wipe and reseed.

## Data-change checklist for future agents

When changing data/storage behavior:

1. Update `models.py` first.
2. Decide whether request/response schemas need new fields or compatibility shims.
3. Generate and inspect an Alembic migration.
4. Check whether tests using direct `SQLModel.metadata.create_all` still exercise migration-only defaults or constraints.
5. Update route-level eager loading if responses/templates need relationships.
6. Update browser templates/JS for new fields.
7. Update seed data if demo behavior should show the new feature.
8. Review deployment docs for new environment variables or external services.

## Storage watch points

- The Docker and VPS setups rely on environment variables; `.env` is ignored and should remain secret.
- `S3_ENDPOINT_URL` affects the boto3 client but not the computed public `image_path` URL.
- `MAX_UPLOAD_SIZE_BYTES` defaults to 5 MiB; `vps_setup.txt` aligns nginx `client_max_body_size` to 5M.
- Object deletion happens after DB commits in profile flows, so old/orphan S3 objects are possible on partial failures.
- `posts.likes` exists at the database layer but has no product behavior yet.
