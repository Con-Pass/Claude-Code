from embedding_pipeline_config import embedding_pipeline_config
from llama_index.embeddings.openai import OpenAIEmbedding
from typing import Optional

# Singleton instance for model reuse
_embedding_model: Optional[OpenAIEmbedding] = None


def get_embedding_model() -> OpenAIEmbedding:
    """
    Get or create a singleton embedding model.
    Reuses model instance across requests for better performance.
    """
    global _embedding_model

    if _embedding_model is None:
        _embedding_model = OpenAIEmbedding(
            model=embedding_pipeline_config.EMBEDDING_MODEL,
            dimensions=embedding_pipeline_config.EMBEDDING_DIM,
            api_key=embedding_pipeline_config.OPENAI_API_KEY,
            timeout=60.0,
            max_retries=3,
        )

    return _embedding_model
