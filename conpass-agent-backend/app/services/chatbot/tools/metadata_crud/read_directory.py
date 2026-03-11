from typing import List, Dict, Any

from llama_index.core.tools import FunctionTool

from app.services.conpass_api_service import ConpassApiService
from app.core.logging_config import get_logger

logger = get_logger(__name__)

async def read_directory(conpass_api_service: ConpassApiService) -> List[Dict[str, Any]]:
    """
    Tool to read available directories from ConPass API.
    
    Returns list of directories with their IDs and names that the user has access to.
    """
    logger.info("[READ_DIRECTORY] Fetching allowed directories")
    return await conpass_api_service.get_allowed_directories_with_names()


def get_read_directory_tool(conpass_api_service: ConpassApiService):
    """
    Creates and returns the read_directory tool function.
    """

    return FunctionTool.from_defaults(
        async_fn=read_directory,
        name="read_directory",
        description=(
            "Read directory information including directory names and directory ids. "
            "Use this to understand which directories are accessed by the user"
            "\n\n"
            "RETURNS:\n"
            "List of Dict containing:\n"
            "- directory_id: Unique identifier for the directory\n"
            "- directory_name: Name of the directory\n"
            "\n\n"
            "WHEN TO USE:\n"
            "- When you want to know which directories are accessible.\n"
            "- To fetch directory id(s) and name(s)"
            "- To update directory metadata operation such as visibility enable or disable etc."
        ),
        partial_params={
            "conpass_api_service": conpass_api_service,
        },
    )

