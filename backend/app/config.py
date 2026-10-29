from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Attilan"
    ENVIRONMENT: str = "production"

    # Empty values intentionally fail closed at connection/authentication time.
    # No development credentials are embedded in application code.
    DATABASE_URL: str = Field(default="")
    MINIO_ENDPOINT: str = Field(default="")
    MINIO_ACCESS_KEY: str = Field(default="")
    MINIO_SECRET_KEY: str = Field(default="")
    MINIO_SECURE: bool = Field(default=True)
    MINIO_EVIDENCE_BUCKET: str = Field(default="")
    MINIO_RETENTION_YEARS: int = Field(default=10, ge=1)

    JWT_SECRET_KEY: str = Field(default="")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ISSUER: str = Field(default="")
    JWT_AUDIENCE: str = Field(default="")
    CORS_ALLOWED_ORIGINS: str = Field(default="")

    @field_validator("DATABASE_URL")
    @classmethod
    def require_bounded_database_identity(cls, value: str) -> str:
        if not value:
            return value
        username = urlparse(value).username
        if username not in {"api_worker_login", "api_worker"}:
            raise ValueError("DATABASE_URL must authenticate through the api_worker role boundary")
        return value

    @field_validator("JWT_ALGORITHM")
    @classmethod
    def permit_only_hmac_sha256(cls, value: str) -> str:
        if value != "HS256":
            raise ValueError("JWT_ALGORITHM must be HS256 until asymmetric issuer keys are deployed")
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
