from llama_index.core.settings import Settings

from app.core.config import settings as app_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def init_model_settings():
    model_provider = app_settings.MODEL_PROVIDER
    match model_provider:
        case "openai":
            init_openai()
        # case "gemini":
        #     init_gemini()
        case "azure-openai":
            init_azure_openai()
        case _:
            raise ValueError(f"Invalid model provider: {model_provider}")

    Settings.chunk_size = app_settings.CHUNK_SIZE
    Settings.chunk_overlap = app_settings.CHUNK_OVERLAP

    # Initialize sparse embedding model for hybrid search at startup
    try:
        from app.services.chatbot.tools.semantic_search.sparse_query import (
            get_sparse_embedding_model,
        )

        get_sparse_embedding_model()  # Initialize at startup
        logger.info("Sparse embedding model initialized for hybrid search")
    except Exception as e:
        logger.warning(
            f"Failed to initialize sparse embedding model: {e}. "
            "Hybrid search will use dense-only fallback."
        )
        # Don't raise - allow app to start, but hybrid search will fallback


def init_openai():
    from llama_index.core.constants import DEFAULT_TEMPERATURE
    from llama_index.embeddings.openai import OpenAIEmbedding
    from llama_index.llms.openai import OpenAIResponses

    max_tokens = app_settings.LLM_MAX_TOKENS
    model_name = app_settings.MODEL
    temperature = (
        app_settings.LLM_TEMPERATURE
        if app_settings.LLM_TEMPERATURE is not None
        else DEFAULT_TEMPERATURE
    )
    # Settings.llm = OpenAI(
    #     model=model_name,
    #     api_key=app_settings.OPENAI_API_KEY,
    #     temperature=float(temperature),
    #     max_tokens=int(max_tokens) if max_tokens is not None else None,
    # )

    Settings.llm = OpenAIResponses(
        model=model_name,
        api_key=app_settings.OPENAI_API_KEY,
        temperature=float(temperature),
        max_tokens=max_tokens,
        reasoning_options={"effort": "low"},
        additional_kwargs={
            "parallel_tool_calls": False,
        },
        timeout=30,
        max_retries=2,
    )

    if app_settings.EMBEDDING_PROVIDER == "bge-m3":
        _init_bge_m3()
    elif app_settings.EMBEDDING_PROVIDER == "fastembed":
        _init_fastembed()
    else:
        dimensions = app_settings.EMBEDDING_DIM
        Settings.embed_model = OpenAIEmbedding(
            model=app_settings.EMBEDDING_MODEL,
            dimensions=int(dimensions) if dimensions is not None else None,
            api_key=app_settings.OPENAI_API_KEY,
        )


def _init_bge_m3():
    """
    BGE-M3 を LlamaIndex の embed_model として設定する。

    Dense ベクトル (1024次元) の生成に使用する。
    Sparse ベクトルは sparse_query.py が BGE-M3 から直接取得する。
    """
    from llama_index.core.embeddings import BaseEmbedding
    from llama_index.core.bridge.pydantic import Field
    from typing import List as _List

    class BGEM3Embedding(BaseEmbedding):
        """BGE-M3 Dense ベクトルを LlamaIndex インターフェースで提供するアダプタ。"""

        model_name: str = Field(default="BAAI/bge-m3")

        @classmethod
        def class_name(cls) -> str:
            return "BGEM3Embedding"

        def _get_query_embedding(self, query: str) -> _List[float]:
            from app.services.bge_m3 import encode_single_dense
            return encode_single_dense(query)

        def _get_text_embedding(self, text: str) -> _List[float]:
            from app.services.bge_m3 import encode_single_dense
            return encode_single_dense(text)

        def _get_text_embeddings(self, texts: _List[str]) -> _List[_List[float]]:
            from app.services.bge_m3 import encode_texts
            result = encode_texts(texts, return_dense=True, return_sparse=False)
            return [v.tolist() for v in result["dense_vecs"]]

        async def _aget_query_embedding(self, query: str) -> _List[float]:
            import asyncio
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._get_query_embedding, query)

        async def _aget_text_embedding(self, text: str) -> _List[float]:
            import asyncio
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._get_text_embedding, text)

    # BGE-M3 シングルトンを起動時にロード（モデルキャッシュのウォームアップ）
    from app.services.bge_m3 import get_bge_m3_model
    get_bge_m3_model()

    Settings.embed_model = BGEM3Embedding()
    logger.info("BGE-M3 embedding model initialized (1024-dim dense)")


def _init_fastembed():
    try:
        from llama_index.embeddings.fastembed import FastEmbedEmbedding
    except ImportError:
        raise ImportError(
            "FastEmbed support is not installed. "
            "Please run: pip install llama-index-embeddings-fastembed"
        )

    model_name = app_settings.EMBEDDING_MODEL
    Settings.embed_model = FastEmbedEmbedding(model_name=model_name)
    logger.info(f"FastEmbed embedding model initialized: {model_name}")


def init_azure_openai():
    from llama_index.core.constants import DEFAULT_TEMPERATURE

    try:
        from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
        from llama_index.llms.azure_openai import AzureOpenAI
    except ImportError:
        raise ImportError(
            "Azure OpenAI support is not installed. Please install it with `poetry add llama-index-llms-azure-openai` and `poetry add llama-index-embeddings-azure-openai`"
        )

    if not app_settings.AZURE_OPENAI_LLM_DEPLOYMENT:
        raise ValueError("AZURE_OPENAI_LLM_DEPLOYMENT is required for Azure OpenAI")
    if not app_settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT:
        raise ValueError(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT is required for Azure OpenAI"
        )
    if not app_settings.AZURE_OPENAI_API_KEY:
        raise ValueError("AZURE_OPENAI_API_KEY is required for Azure OpenAI")
    if not app_settings.AZURE_OPENAI_ENDPOINT:
        raise ValueError("AZURE_OPENAI_ENDPOINT is required for Azure OpenAI")

    llm_deployment = app_settings.AZURE_OPENAI_LLM_DEPLOYMENT
    embedding_deployment = app_settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT
    max_tokens = app_settings.LLM_MAX_TOKENS
    temperature = (
        app_settings.LLM_TEMPERATURE
        if app_settings.LLM_TEMPERATURE is not None
        else DEFAULT_TEMPERATURE
    )
    dimensions = app_settings.EMBEDDING_DIM

    azure_config = {
        "api_key": app_settings.AZURE_OPENAI_API_KEY,
        "azure_endpoint": app_settings.AZURE_OPENAI_ENDPOINT,
        "api_version": app_settings.AZURE_OPENAI_API_VERSION
        or app_settings.OPENAI_API_VERSION,
    }

    Settings.llm = AzureOpenAI(
        model=app_settings.MODEL,
        max_tokens=int(max_tokens) if max_tokens is not None else None,
        temperature=float(temperature),
        deployment_name=llm_deployment,
        **azure_config,
    )

    Settings.embed_model = AzureOpenAIEmbedding(
        model=app_settings.EMBEDDING_MODEL,
        dimensions=int(dimensions) if dimensions is not None else None,
        deployment_name=embedding_deployment,
        **azure_config,
    )


def init_gemini():
    try:
        from llama_index.llms.google_genai import GoogleGenAI

    except ImportError:
        raise ImportError("Gemini support is not installed.")

    model_name = "gemini-2.5-flash"
    api_key = app_settings.GOOGLE_AI_API_KEY

    Settings.llm = GoogleGenAI(model=model_name, api_key=api_key)
