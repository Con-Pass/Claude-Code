from fastapi import APIRouter, Request, HTTPException, status
from app.core.logging_config import get_logger

scope_router = r = APIRouter()

logger = get_logger(__name__)


@r.get(
    "",
    summary="Get Scope",
    description="Get the scope of the current user",
    tags=["scope"],
)
async def get_scope(request: Request) -> bool:
    # Middleware populates request.state.conpass_token after basic validation.
    allowed_scope = "write:chatbot"
    conpass_jwt = getattr(request.state, "conpass_token", None)
    if not conpass_jwt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing ConPass authentication token.",
        )
    scope = getattr(request.state, "scope", None)
    if scope == allowed_scope:
        return True

    return False
