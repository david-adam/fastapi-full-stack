from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

    database_url: str
    database_url_direct: str

    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    max_upload_size_bytes: int = 5 * 1024 * 1024

    s3_bucket_name:str
    s3_region: str = "ap-southeast-1"
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None
    s3_endpoint_url: str | None = None

    # CloudFront delivery — optional. When unset, app-generated URLs fall
    # back to direct S3 (compatibility mode). The value should be the scheme
    # + host (no trailing slash), e.g. "https://d111111abcdef8.cloudfront.net".
    cloudfront_base_url: str | None = None 


    posts_per_page: int = 10

    reset_token_expire_minutes: int = 60


    mail_server: str = "localhost"
    mail_port: int = 587
    mail_username: str = ""
    mail_password: SecretStr = SecretStr("")
    mail_from: str = "noreply@example.com"
    mail_use_tls: bool = True

    frontend_url: str = "http://localhost:8000"

settings = Settings() # Loaded from .env file