import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    PROJECT_NAME: str = "OpenCase-BD Evidence Integrity Platform"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")

    # Database
    DATABASE_URL: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/opencase_bd"
        ),
        description="Async PostgreSQL connection string",
    )

    # MinIO / S3 WORM Storage
    MINIO_ENDPOINT: str = Field(
        default_factory=lambda: os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        description="MinIO S3 Host:Port",
    )
    MINIO_ACCESS_KEY: str = Field(
        default_factory=lambda: os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        description="MinIO Access Key",
    )
    MINIO_SECRET_KEY: str = Field(
        default_factory=lambda: os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        description="MinIO Secret Key",
    )
    MINIO_SECURE: bool = Field(
        default_factory=lambda: os.getenv("MINIO_SECURE", "false").lower() == "true",
        description="Use TLS/SSL for MinIO",
    )
    MINIO_EVIDENCE_BUCKET: str = Field(
        default_factory=lambda: os.getenv("MINIO_EVIDENCE_BUCKET", "opencase-evidence-worm"),
        description="Write-Once-Read-Many bucket with Object Lock enabled",
    )
    MINIO_RETENTION_YEARS: int = Field(
        default_factory=lambda: int(os.getenv("MINIO_RETENTION_YEARS", "7")),
        description="WORM retention period in years",
    )

    # JWT Authentication
    JWT_SECRET_KEY: str = Field(
        default_factory=lambda: os.getenv("JWT_SECRET_KEY", ""),
        description="HMAC secret key for JWT validation",
    )
    JWT_ALGORITHM: str = "HS256"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
