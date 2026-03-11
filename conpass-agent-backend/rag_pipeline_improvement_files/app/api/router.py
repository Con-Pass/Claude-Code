from fastapi import APIRouter

from app.api.v1.chat import chat_router  # noqa: F401
from app.api.v1.chat_config import config_router  # noqa: F401
from app.api.v1.chat_non_streaming import chat_non_streaming_router  # noqa: F401
from app.api.v1.chat_history import chat_history_router  # noqa: F401
from app.api.v1.metadata_crud import metadata_crud_router  # noqa: F401

# from app.api.v1.directories import directories_router  # noqa: F401
from app.api.v1.ocr import ocr_router  # noqa: F401

from app.api.v1.upload import file_upload_router  # noqa: F401
from app.api.v1.feedback import feedback_router  # noqa: F401

# from app.api.v1.query import query_router  # noqa: F401
from app.api.v1.scope import scope_router  # noqa: F401

api_router = APIRouter()
api_router.include_router(chat_router, prefix="/v1/chat", tags=["chat"])
api_router.include_router(config_router, prefix="/v1/chat/config", tags=["config"])
api_router.include_router(
    chat_non_streaming_router, prefix="/v1/chat/non-streaming", tags=["chat"]
)
api_router.include_router(chat_history_router, prefix="/v1/chat", tags=["chat"])
api_router.include_router(
    metadata_crud_router, prefix="/v1/metadata", tags=["metadata-crud"]
)
# api_router.include_router(
#     directories_router, prefix="/v1/directories", tags=["directories"]
# )
api_router.include_router(ocr_router, prefix="/v1/ocr", tags=["ocr"])
api_router.include_router(file_upload_router, prefix="/v1/chat/upload", tags=["chat"])
# api_router.include_router(query_router, prefix="/v1/query", tags=["query"])
api_router.include_router(scope_router, prefix="/v1/scope", tags=["scope"])
api_router.include_router(file_upload_router, prefix="/v1/files", tags=["files"])
api_router.include_router(feedback_router, prefix="/v1/feedback", tags=["feedback"])
