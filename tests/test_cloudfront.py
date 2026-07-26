"""CloudFront URL delivery + S3-fallback behavior."""

from io import BytesIO
from pathlib import Path

import pytest
from httpx import AsyncClient

from models import build_media_url
from tests.conftest import auth_header, create_test_user, login_user


def test_build_media_url_uses_s3_when_cloudfront_unset():
    from config import settings

    settings.cloudfront_base_url = None
    url = build_media_url("profile_pics/abc.jpg")
    assert url == (
        f"https://{settings.s3_bucket_name}.s3."
        f"{settings.s3_region}.amazonaws.com/profile_pics/abc.jpg"
    )
    assert "cloudfront" not in url


def test_build_media_url_uses_cloudfront_when_configured():
    from config import settings

    settings.cloudfront_base_url = "https://d111111abcdef8.cloudfront.net"
    try:
        url = build_media_url("profile_pics/abc.jpg")
    finally:
        settings.cloudfront_base_url = None

    assert url == "https://d111111abcdef8.cloudfront.net/profile_pics/abc.jpg"
    assert "s3.amazonaws.com" not in url


def test_build_media_url_strips_trailing_slash_from_cloudfront_base():
    from config import settings

    settings.cloudfront_base_url = "https://d111111abcdef8.cloudfront.net/"
    try:
        url = build_media_url("profile_pics/abc.jpg")
    finally:
        settings.cloudfront_base_url = None

    assert url == "https://d111111abcdef8.cloudfront.net/profile_pics/abc.jpg"


@pytest.mark.anyio
async def test_image_path_uses_s3_fallback_by_default(
    client: AsyncClient,
    mocked_aws,
):
    from config import settings

    settings.cloudfront_base_url = None
    user = await create_test_user(client)
    token = await login_user(client)

    test_image_path = Path(__file__).parent / "test_image.jpg"
    image_bytes = test_image_path.read_bytes()

    response = await client.patch(
        f"/api/users/{user['id']}/picture",
        files={"file": ("profile.jpg", BytesIO(image_bytes), "image/jpeg")},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["image_file"] is not None
    # S3 fallback path — same shape as before.
    assert data["image_path"].startswith(
        f"https://{settings.s3_bucket_name}.s3."
    )
    assert data["image_path"].endswith(f"/profile_pics/{data['image_file']}")


@pytest.mark.anyio
async def test_image_path_uses_cloudfront_when_configured(
    client: AsyncClient,
    mocked_aws,
):
    from config import settings

    settings.cloudfront_base_url = "https://d111111abcdef8.cloudfront.net"
    try:
        user = await create_test_user(client)
        token = await login_user(client)

        test_image_path = Path(__file__).parent / "test_image.jpg"
        image_bytes = test_image_path.read_bytes()

        response = await client.patch(
            f"/api/users/{user['id']}/picture",
            files={"file": ("profile.jpg", BytesIO(image_bytes), "image/jpeg")},
            headers=auth_header(token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["image_file"] is not None
        assert data["image_path"].startswith(
            "https://d111111abcdef8.cloudfront.net/"
        )
        assert data["image_path"].endswith(f"/profile_pics/{data['image_file']}")
        assert "s3.amazonaws.com" not in data["image_path"]

        # Upload still went to S3 — CDN is delivery only.
        s3_objects = mocked_aws.list_objects_v2(Bucket="test-bucket")
        assert "Contents" in s3_objects
        assert any(
            obj["Key"].endswith(data["image_file"]) for obj in s3_objects["Contents"]
        )
    finally:
        settings.cloudfront_base_url = None


@pytest.mark.anyio
async def test_default_image_path_is_unchanged_by_cloudfront(client: AsyncClient):
    from config import settings

    settings.cloudfront_base_url = "https://d111111abcdef8.cloudfront.net"
    try:
        response = await client.post(
            "/api/users",
            json={
                "username": "defaultpic",
                "email": "default@example.com",
                "password": "password123",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["image_file"] is None
        # No uploaded file → falls through to the local static default,
        # independent of CDN config.
        assert data["image_path"] == "/static/profile_pics/default.jpg"
    finally:
        settings.cloudfront_base_url = None