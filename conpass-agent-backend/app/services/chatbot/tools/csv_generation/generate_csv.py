import csv
import io
import json
from typing import Any, Dict, List, Union
from pydantic import BaseModel, Field, ConfigDict

from app.core.config import settings
from app.core.logging_config import get_logger
from llama_index.llms.openai import OpenAIResponses
from app.services.chatbot.tools.csv_generation.prompts import (
    CSV_GENERATION_PROMPT_TEMPLATE,
)

logger = get_logger(__name__)


class CSVData(BaseModel):
    """Schema for structured CSV generation output."""
    
    model_config = ConfigDict(
        extra="forbid",  # Required for OpenAI structured output
    )
    
    filename: str = Field(
        description="A descriptive filename for the CSV, ending in .csv (e.g., 'contract_summary.csv')"
    )
    headers: List[str] = Field(description="List of column headers for the CSV")
    rows: List[Dict[str, Any]] = Field(
        description="List of rows, where each row is a dictionary with keys matching the headers"
    )


async def generate_csv_logic(
    data: Union[List[Dict[str, Any]], Dict[str, Any]], instruction: str
) -> Dict[str, Any]:
    """
    Generates a CSV string based on the provided data and instruction using an LLM.

    Args:
        data: List of dictionaries containing the source data (e.g., contracts, metadata).
        instruction: User's instruction on how to generate the CSV.

    Returns:
        Dict containing success status, csv_content, filename, and message.
    """
    logger.info(f"Generating CSV with instruction: {instruction}")

    if not data:
        return {
            "success": False,
            "message": "No data provided for CSV generation.",
        }

    try:
        # Convert data to string for the prompt, handling potentially large payloads
        # Truncate if necessary (basic protection, though model context is large)
        data_str = json.dumps(data, ensure_ascii=False, indent=2)

        # Determine model based on complexity/size (defaulting to gpt-4o-mini for speed/cost)
        # Using a structured LLM to enforce the CSVData schema
        llm = OpenAIResponses(
            model="gpt-4o-mini",
            temperature=0.1,
            api_key=settings.OPENAI_API_KEY,
        )

        sllm = llm.as_structured_llm(CSVData)

        prompt = CSV_GENERATION_PROMPT_TEMPLATE.format(
            instruction=instruction, data_context=data_str
        )

        response = await sllm.acomplete(prompt)

        # `acomplete()` returns a CompletionResponse.
        # When using `as_structured_llm`, the parsed structured output is available in `response.raw`.
        # Use model_dump().get("raw", {}) pattern for safer access (matches perform_analysis.py).
        
        res_data = response.model_dump().get("raw", {})
        if not res_data:
            # Check if response.text exists as fallback (sometimes happens if structure fails but text is generated)
            if hasattr(response, "text") and response.text:
                logger.warning(
                    "LLM returned text instead of structured data. Attempting to parse JSON from text."
                )
                try:
                    # Try to parse the text as JSON
                    parsed = json.loads(response.text)
                    if isinstance(parsed, dict):
                        res_data = parsed
                    else:
                        logger.error("LLM returned non-dict JSON structure.")
                        return {
                            "success": False,
                            "message": "Failed to generate structured data for CSV.",
                        }
                except json.JSONDecodeError:
                    logger.error("LLM returned plain text that cannot be parsed as JSON.")
                    return {
                        "success": False,
                        "message": "Failed to generate structured data for CSV.",
                    }
            else:
                logger.error("LLM failed to return structured data.")
                return {
                    "success": False,
                    "message": "Failed to generate structured data for CSV.",
                }

        # Validate with Pydantic model to be safe
        if isinstance(res_data, CSVData):
            csv_data = res_data
        elif isinstance(res_data, dict):
            try:
                csv_data = CSVData(**res_data)
            except Exception as e:
                logger.error(f"Failed to validate CSVData from LLM response: {e}")
                return {
                    "success": False,
                    "message": f"LLM generated invalid structured data for CSV: {str(e)}",
                }
        else:
            logger.error(
                f"LLM generated invalid structured data type: {type(res_data)}"
            )
            return {
                "success": False,
                "message": "LLM generated invalid structured data for CSV.",
            }

        # Generate CSV string
        output = io.StringIO()
        if not csv_data.headers:
            return {
                "success": False,
                "message": "LLM generated no headers for the CSV.",
            }

        writer = csv.DictWriter(output, fieldnames=csv_data.headers)
        writer.writeheader()
        writer.writerows(csv_data.rows)

        csv_content = output.getvalue()

        # Use generated filename or fallback
        final_filename = (
            csv_data.filename if csv_data.filename else "generated_data.csv"
        )
        if not final_filename.endswith(".csv"):
            final_filename += ".csv"

        logger.info(f"Generated CSV content with file name: {final_filename}")
        return {
            "success": True,
            "csv_content": csv_content,
            "filename": final_filename,
            "message": "CSV generated successfully.",
        }

    except Exception as e:
        logger.exception(f"Error generating CSV: {e}")
        return {
            "success": False,
            "message": f"An error occurred during CSV generation: {str(e)}",
        }
