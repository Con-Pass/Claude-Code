from app.core.logging_config import get_logger
from fastapi import APIRouter, Request, HTTPException, status
from app.services.conpass_api_service import get_conpass_api_service
from app.schemas.general import GeneralResponse

directories_router = r = APIRouter()

logger = get_logger(__name__)


@r.get(
    "/allowed",
    summary="Get Allowed Directory IDs",
    description="Retrieve list of allowed directory IDs from ConPass API",
    response_description="List of allowed directory IDs",
    response_model=GeneralResponse,
    tags=["directories"],
)
async def get_allowed_directories(request: Request) -> GeneralResponse:
    """
    Get the list of allowed directory IDs for the authenticated user.

    This endpoint:
    - Fetches allowed directories from ConPass API
    - Extracts and returns only the directory IDs
    - Requires valid ConPass authentication token

    **Response:**
    - `status`: "success" or "error"
    - `description`: Description of the response
    - `data`: List of directory IDs (e.g., [1, 2, 3, ...])

    **Use Case:**
    - Filter contracts by allowed directories
    - Validate directory access permissions
    - Display user-specific directory list

    **Example Response:**
    ```json
    {
        "status": "success",
        "description": "Allowed directory IDs fetched successfully",
        "data": [1, 5, 12, 23]
    }
    ```
    """
    try:
        # Middleware populates request.state.conpass_token after validation
        conpass_jwt = getattr(request.state, "conpass_token", None)
        if not conpass_jwt:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing ConPass authentication token.",
            )

        # Create ConPass API service instance
        conpass_service = get_conpass_api_service(conpass_jwt)

        # Fetch allowed directories
        result = await conpass_service.get_allowed_directories()

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching allowed directories: {e}", exc_info=True)
        return GeneralResponse(
            status="error",
            description="Error fetching allowed directories from ConPass API",
        )
