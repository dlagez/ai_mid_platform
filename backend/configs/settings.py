from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg2://postgres:postgres@postgres:5432/ai_mid_platform"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_documents: str = "documents"
    minio_bucket_indexes: str = "rag-indexes"

    document_parser_provider: str = "ppocr"

    ppocr_base_url: str | None = None
    ppocr_layout_parsing_endpoint: str = "/layout-parsing"
    ppocr_api_key: str | None = None
    ppocr_api_key_header: str = "Authorization"
    ppocr_timeout_seconds: int = 300
    ppocr_format_block_content: bool = True
    ppocr_use_seal_recognition: bool = True
    ppocr_use_ocr_for_image_block: bool = True

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
