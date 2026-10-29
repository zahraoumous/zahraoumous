from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DATAPILOT_", extra="ignore")
    database_url: SecretStr
    redis_url: SecretStr
    s3_endpoint: str
    s3_access_key: SecretStr
    s3_secret_key: SecretStr
    s3_region: str = "us-east-1"
    s3_bucket: str = "datapilot"
    app_origin: str = "http://localhost:3000"
    cookie_secure: bool = False
    ai_key_encryption_secret: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
