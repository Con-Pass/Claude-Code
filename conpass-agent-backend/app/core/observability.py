from langfuse import get_client
from app.core.config import settings
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def init_observability():
    if (
        settings.LANGFUSE_HOST
        and settings.LANGFUSE_PUBLIC_KEY
        and settings.LANGFUSE_SECRET_KEY
    ):
        try:
            langfuse = get_client()
            # Verify connection
            if langfuse.auth_check():
                logger.info("Langfuse client is authenticated and ready!")

                LlamaIndexInstrumentor().instrument()
            else:
                logger.error(
                    "Authentication failed. Please check your credentials and host."
                )
        except Exception:
            logger.exception("Error initializing observability")
