from embedding_pipeline_config import embedding_pipeline_config
from typing import Optional, Union

# Singleton instance for model reuse
_embedding_model = None


def get_embedding_model():
    """
    Get or create a singleton embedding model.
    Uses FastEmbed if EMBEDDING_PROVIDER=fastembed, otherwise OpenAI.
    """
    global _embedding_model

    if _embedding_model is None:
        if embedding_pipeline_config.EMBEDDING_PROVIDER == "fastembed":
            from llama_index.embeddings.fastembed import FastEmbedEmbedding
            _embedding_model = FastEmbedEmbedding(
                model_name=embedding_pipeline_config.EMBEDDING_MODEL,
            )
        else:
            from llama_index.embeddings.openai import OpenAIEmbedding
            _embedding_model = OpenAIEmbedding(
                model=embedding_pipeline_config.EMBEDDING_MODEL,
                dimensions=embedding_pipeline_config.EMBEDDING_DIM,
                api_key=embedding_pipeline_config.OPENAI_API_KEY,
                timeout=60.0,
                max_retries=3,
            )

    return _embedding_model
