from pydantic_settings import BaseSettings, SettingsConfigDict


class EmbeddingPipelineConfig(BaseSettings):
    CHUNK_SIZE: int
    CHUNK_OVERLAP: int

    QDRANT_URL: str
    QDRANT_API_KEY: str
    QDRANT_COLLECTION: str

    EMBEDDING_PROVIDER: str = "openai"  # "openai" or "fastembed"
    EMBEDDING_MODEL: str
    EMBEDDING_DIM: int
    OPENAI_API_KEY: str

    # SUMMARY_MODEL: str

    REDIS_URL: str

    model_config = SettingsConfigDict(
        extra="allow",
        env_file=".env",
        case_sensitive=True,
        env_file_encoding="utf-8",
        env_file_required=False,
    )


embedding_pipeline_config = EmbeddingPipelineConfig()
