import json
from typing import Any, Dict, List, Union

from app.core.config import settings
from app.core.logging_config import get_logger
from llama_index.llms.openai import OpenAI
from app.services.chatbot.tools.document_diffing.prompts import (
    DIFF_GENERATION_PROMPT,
)

logger = get_logger(__name__)


async def generate_diff_logic(
    data: Union[List[Dict[str, Any]], Dict[str, Any]], instruction: str
) -> Dict[str, Any]:
    """
    Generates a text-based diff report based on the provided data and instruction using an LLM.

    Args:
        data: List of dictionaries or Dictionary containing the source text data.
        instruction: User's instruction on how to generate the diff.

    Returns:
        Dict containing success status, diff_content, and message.
    """
    logger.info(f"Generating diff with instruction: {instruction}")

    if not data:
        return {
            "success": False,
            "message": "No data provided for document diffing.",
        }

    try:
        # Preprocess data to extract document count and labels
        if isinstance(data, dict):
            num_documents = len(data)
            document_labels = list(data.keys())
            logger.info(f"Data is a dictionary with {num_documents} document(s). Keys: {document_labels}")
        elif isinstance(data, list):
            num_documents = len(data)
            document_labels = [f"Document {i+1}" for i in range(len(data))]
            logger.info(f"Data is a list with {num_documents} document(s).")
        else:
            num_documents = 1
            document_labels = ["Document 1"]
            logger.warning(f"Data is neither dict nor list, treating as single document. Type: {type(data)}")

        # Convert data to string for the prompt
        data_str = json.dumps(data, ensure_ascii=False, indent=2)

        # Create a summary header for the prompt
        document_summary = f"""
**DOCUMENT COUNT SUMMARY:**
- Total number of documents to compare: {num_documents}
- Document identifiers/labels: {', '.join(document_labels)}

**IMPORTANT**: You have {num_documents} document(s) to compare. {"You MUST compare all of them." if num_documents >= 2 else "You need at least 2 documents to perform a comparison. Please inform the user that comparison requires at least two documents."}

"""

        # Using gpt-4o-mini for efficiency, similar to csv_generation tool
        llm = OpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            api_key=settings.OPENAI_API_KEY,
        )

        prompt = DIFF_GENERATION_PROMPT.format(
            instruction=instruction,
            document_count=num_documents,
            document_summary=document_summary,
            data=data_str
        )

        response = await llm.acomplete(prompt)
        diff_content = response.text

        logger.info("Generated diff content successfully.")
        return {
            "success": True,
            "diff_content": diff_content,
            "message": "Document diff generated successfully.",
        }

    except Exception as e:
        logger.exception(f"Error generating diff: {e}")
        return {
            "success": False,
            "message": f"An error occurred during diff generation: {str(e)}",
        }
