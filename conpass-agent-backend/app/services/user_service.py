from typing import Optional
import httpx
from app.core.logging_config import get_logger
from app.core.config import settings

logger = get_logger(__name__)


async def get_user_id_from_token(conpass_jwt: str) -> Optional[str]:
    """
    Extract user_id from ConPass JWT token by calling the ConPass API /user endpoint.

    Args:
        conpass_jwt: The ConPass authentication token

    Returns:
        user_id string if successful, None otherwise

    Raises:
        Exception: If the API call fails or user_id cannot be extracted
    """
    try:
        # Call the ConPass API /user endpoint to get user information
        # Response format: {"id": 172, "username": "...", "email": "...", ...}
        user_url = f"{settings.CONPASS_API_BASE_URL}/user"

        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.get(
                user_url,
                headers={"Accept": "application/json"},
                cookies={"auth-token": conpass_jwt},
            )
            response.raise_for_status()
            user_data = response.json()

            # Extract user_id from the response
            # ConPass API returns: {"id": 172, "username": "...", "email": "...", ...}
            user_id = None
            if isinstance(user_data, dict):
                # Primary field: "id" (e.g., 172)
                user_id = user_data.get("id")

                # Fallback to other possible field names (for robustness)
                if not user_id:
                    user_id = user_data.get("user_id") or user_data.get("userId")

                # If user_id is nested in a "user" object (unlikely but handle for safety)
                if (
                    not user_id
                    and "user" in user_data
                    and isinstance(user_data["user"], dict)
                ):
                    user_id = (
                        user_data["user"].get("id")
                        or user_data["user"].get("user_id")
                        or user_data["user"].get("userId")
                    )

            if not user_id:
                logger.error(
                    f"Could not extract user_id from ConPass API response: {user_data}"
                )
                return None

            logger.debug(f"Successfully extracted user_id: {user_id}")
            return str(user_id)

    except httpx.HTTPStatusError as exc:
        logger.error(
            f"ConPass API returned error status {exc.response.status_code} when fetching user: {exc.response.text}"
        )
        raise Exception(f"Failed to fetch user information: {exc.response.status_code}")
    except httpx.RequestError as exc:
        logger.error(f"Error contacting ConPass API /user endpoint: {exc}")
        raise Exception("Unable to reach ConPass authentication service")
    except Exception as exc:
        logger.exception(f"Unexpected error extracting user_id: {exc}")
        raise
