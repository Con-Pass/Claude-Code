"""
ユーザーフィードバック収集API。

チャットの検索結果やレスポンスに対するフィードバックをFirestoreに保存する。
"""

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from google.cloud import firestore

from app.core.config import settings
from app.core.logging_config import get_logger
from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.services.user_service import get_user_id_from_token

logger = get_logger(__name__)

feedback_router = APIRouter()

# Firestore collection name
FEEDBACK_COLLECTION = "chat_feedback"


def _get_firestore_client() -> firestore.AsyncClient:
    return firestore.AsyncClient(
        project=settings.FIRESTORE_PROJECT_ID,
        database=settings.FIRESTORE_DATABASE_ID,
    )


@feedback_router.post(
    "",
    response_model=FeedbackResponse,
    summary="Submit feedback",
    description="Submit feedback for a chat message or search result",
    tags=["feedback"],
)
async def submit_feedback(
    request: Request,
    data: FeedbackRequest,
):
    """
    ユーザーフィードバックをFirestoreに保存する。

    フィードバックはsession_idとmessage_idでチャット履歴に紐付けられる。
    """
    try:
        conpass_jwt = getattr(request.state, "conpass_token", None)
        if not conpass_jwt:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing ConPass authentication token.",
            )

        user_id = await get_user_id_from_token(conpass_jwt)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to retrieve user information.",
            )

        feedback_id = str(uuid4())

        feedback_doc = {
            "feedback_id": feedback_id,
            "user_id": user_id,
            "session_id": data.session_id,
            "message_id": data.message_id,
            "rating": data.rating,
            "comment": data.comment,
            "tool_used": data.tool_used,
            "result_contract_ids": data.result_contract_ids,
            "created_at": datetime.utcnow().isoformat(),
        }

        db = _get_firestore_client()
        await db.collection(FEEDBACK_COLLECTION).document(feedback_id).set(
            feedback_doc
        )

        logger.info(
            f"Feedback saved: id={feedback_id}, user={user_id}, "
            f"session={data.session_id}, rating={data.rating}"
        )

        return FeedbackResponse(status="success", feedback_id=feedback_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error saving feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save feedback",
        ) from e
