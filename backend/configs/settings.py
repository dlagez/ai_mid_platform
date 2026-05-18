from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg2://postgres:postgres@postgres:5432/ai_mid_platform"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_documents: str = "documents"
    minio_bucket_indexes: str = "rag-indexes"

    docling_base_url: str | None = None
    docling_convert_endpoint: str = "/v1/convert/file"
    docling_legacy_convert_endpoint: str = "/v1alpha/convert/file"
    docling_file_field_name: str = "files"
    docling_api_key: str | None = None
    docling_api_key_header: str = "Authorization"
    docling_timeout_seconds: int = 300

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    adapter_config_path: str = "configs/adapters.yaml"
    litellm_config_path: str = "configs/litellm.yaml"

    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str = "https://cloud.langfuse.com"
    langfuse_tracing_environment: str = "development"
    langfuse_tracing_enabled: bool = True


settings = Settings()
