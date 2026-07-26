# FastAPI blog

A FastAPI + SQLModel blog with user accounts, profile pictures, posts, and
password-reset email.

## Static & media delivery

Profile images are uploaded to **AWS S3** by `image_utils.upload_profile_image`
and removed by `image_utils.delete_profile_image`. S3 stays the storage and
upload backend.

Public URLs returned to clients (e.g. `User.image_path`) are produced by
`models.build_media_url`:

| `CLOUDFRONT_BASE_URL` | Returned URL                                            |
| --------------------- | ------------------------------------------------------- |
| unset                 | `https://{bucket}.s3.{region}.amazonaws.com/{key}`      |
| set                   | `{cloudfront_base_url}/{key}`                           |

The unset case is the legacy direct-S3 behavior and remains a fallback so
existing deployments keep working without a CDN.

### Enabling CloudFront

1. Create a CloudFront distribution with your S3 bucket as the origin.
2. Set `CLOUDFRONT_BASE_URL=https://<your-distribution-domain>` in `.env`
   (see `.env.example`). Do **not** commit `.env`.
3. Restart the app — `image_path` is computed on every response, so no
   database migration or cache flush is needed.

No code change is required to toggle CDN delivery on or off.

## Configuration

All settings come from environment variables (or `.env` in development). See
[`.env.example`](.env.example) for the full list with descriptions.

## Tests

```sh
uv run pytest -q
```

`tests/conftest.py` sets the test database / S3 env vars and uses `moto` to
stub AWS so no real credentials are needed.