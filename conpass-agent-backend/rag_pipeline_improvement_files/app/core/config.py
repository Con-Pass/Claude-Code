from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal, Optional
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseSettings):
    APP_NAME: str = "ConPass Agent"
    ENVIRONMENT: Literal["development", "production", "staging", "test"] = "development"
    STATIC_DIR: str = "static"
    DATA_DIR: str = "data"
    STORAGE_DIR: str = "storage"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8080
    ALLOWED_ORIGINS: str

    # Qdrant settings
    QDRANT_URL: str
    QDRANT_API_KEY: str
    QDRANT_COLLECTION: str

    # File server settings
    FILESERVER_URL_PREFIX: str = "http://localhost:8000/api/files"
    GCS_BUCKET_NAME: str
    CDN_DOMAIN: str
    ASSET_DELIVERY_MODE: Literal["gcs", "cdn"] = "cdn"
    GCS_BROWSER_BASE: str = "https://storage.cloud.google.com"
    SIGNED_URL_TTL_SECONDS: int = 3600  # 1 hour
    UPLOAD_MAX_TOKENS: int = 20000
    TIKTOKEN_ENCODING: str = "cl100k_base"

    # Agent Settings
    MODEL_PROVIDER: str
    MODEL: str
    EMBEDDING_MODEL: str
    EMBEDDING_DIM: Optional[int] = 1024
    OPENAI_API_KEY: str
    GOOGLE_AI_API_KEY: str
    TOP_K: int = 100
    LLM_MAX_TOKENS: int = 200000
    LLM_TEMPERATURE: float = 0.4
    CHUNK_SIZE: int = 1024
    CHUNK_OVERLAP: int = 100

    CONPASS_API_BASE_URL: str
    CONPASS_FRONTEND_BASE_URL: str
    CONPASS_JWT_SECRET: str

    REDIS_URL: str

    # Firestore settings
    FIRESTORE_PROJECT_ID: str
    FIRESTORE_DATABASE_ID: str

    # Prompt settings
    # NEXT_QUESTION_PROMPT: Optional[str] = None
    # CONVERSATION_STARTERS: Optional[str] = None

    # OCR Settings
    OCR_MAX_FILE_MB: int = 10
    TESSERACT_PATH: str = "/usr/bin/tesseract"
    TESSDATA_PREFIX: str = "/usr/share/tesseract-ocr/5/tessdata/"

    # Google Document AI Settings
    GOOGLE_CLOUD_PROJECT_ID: Optional[str] = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
    GOOGLE_CLOUD_LOCATION: str = "us"
    DOCUMENT_AI_PROCESSOR_ID: Optional[str] = os.getenv("DOCUMENT_AI_PROCESSOR_ID")
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = os.getenv(
        "GOOGLE_APPLICATION_CREDENTIALS"
    )
    DOCUMENT_AI_TIMEOUT: int = 30
    DOCUMENT_AI_RETRY_ATTEMPTS: int = 3
    DOCUMENT_AI_PAGE_LIMIT: int = 30

    # Document AI Performance Settings
    DOCUMENT_AI_MAX_WORKERS: int = 4

    # CDN Settings
    CDN_KEY_NAME: str = os.getenv("CDN_KEY_NAME", "cdn-files-key")
    CDN_KEY_B64: str = os.getenv("CDN_KEY_B64", "NhffgQSWGwmaLQuiQayvhQ==")

    # Langfuse observability settings
    LANGFUSE_HOST: Optional[str] = None
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        extra="allow",
        env_file=".env",
        case_sensitive=True,
        env_file_encoding="utf-8",
        # Allow .env file to be missing (for Docker/Cloud Run where env vars are set directly)
        env_file_required=False,
    )


# Lazy initialization - settings loaded on first access
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get settings instance (lazy loading)"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# For backward compatibility - but now it's lazy loaded
class SettingsProxy:
    """Proxy to delay settings initialization until first attribute access"""

    def __getattr__(self, name):
        return getattr(get_settings(), name)

    def __setattr__(self, name, value):
        return setattr(get_settings(), name, value)


settings = SettingsProxy()
