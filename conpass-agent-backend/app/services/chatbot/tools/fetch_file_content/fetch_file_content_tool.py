from typing import Dict
from app.core.logging_config import get_logger
from app.services.file_content_service import FileContentService
from llama_index.core.tools import FunctionTool

logger = get_logger(__name__)


async def get_file_content(file_ids: list[str]) -> Dict[str, str]:
    """
    Retrieves file contents by file IDs.

    Args:
        file_ids: The List of UUIDs of the files to retrieve contents for.

    Returns:
        Dictionary mapping file_id to content string for successful downloads.
        Returns empty dictionary if all downloads fail or an exception occurs.
    """
    try:
        logger.info(f"get_file_content_tool called with file_ids: {file_ids}")
        file_contents: Dict[str, str] = await FileContentService().get_texts_by_ids(
            file_ids=file_ids
        )
        return file_contents

    except Exception as e:
        logger.exception(f"Error retrieving file content for {file_ids}: {e}")
        return {}


def get_file_content_tool() -> FunctionTool:
    """
    Creates a FunctionTool for retrieving file contents by IDs.

    Returns:
        FunctionTool configured for file content retrieval.
    """
    return FunctionTool.from_defaults(
        async_fn=get_file_content,
        name="get_file_content_tool",
        description="""
        Retrieves the extracted text content of files by their list of IDs.
        
        *** FILE ID SCOPE (CRITICAL) ***
        - When the user attaches files in their CURRENT message and asks about them (e.g. summarize, compare, analyze "these files"), pass ONLY the file IDs listed under "=== Files uploaded in this message ===". Do NOT include file IDs from "=== Files from previous messages in this session ===" unless the user explicitly asks for "all files", "every file I uploaded", or "all files in this session".
        - When the user explicitly asks for "all files", "every file I uploaded", "all files in this session", or similar, pass ALL file IDs from both sections.
        - If the current message has no file attachments, you may use file IDs from "=== Files from previous messages in this session ===" as appropriate to the request.
        
        ***IMPORTANT***: Always pass ALL chosen file IDs in a single list in a single call. Do NOT make multiple calls for different files.
        
        Use this tool when:
        - You have file ID(s) and need to read their content
        - User asks to view/read/display content of specific files
        - You need file content for analysis or processing
        - User asks for contracts similar to an uploaded file (then pass the retrieved content or a summary as the query to semantic_search)
        
        Args:
            file_ids: List of UUID strings for all files to retrieve content for
            
        Returns:
            Dictionary mapping file_id (str) to content (str) for successfully retrieved files.
            Only successfully downloaded files are included in the result.
        """,
    )
