"""
Company name extraction service using LLM.
Extracts company names from natural language queries.
"""

from typing import List, Optional
from llama_index.core.settings import Settings as LlamaSettings
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class CompanyNameExtractionResponse(BaseModel):
    """Response schema for company name extraction."""

    company_names: List[str] = Field(
        default_factory=list,
        description="List of company names found in the query. Empty list if no company names found.",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Brief explanation of what company names were identified and why.",
    )


COMPANY_NAME_EXTRACTION_PROMPT = """
You are an expert at extracting company names from natural language queries.

Your task is to identify and extract ALL company names mentioned in the user's query.

## Guidelines

1. **Extract company names exactly as written** - preserve the original text
2. **Include all variations** - if user mentions multiple companies, extract all of them
3. **Japanese and English** - handle both Japanese (株式会社ABC, etc.) and English (ABC Corp, etc.) company names
4. **Context matters** - only extract text that refers to actual company names, not generic terms
5. **Preserve formatting** - keep the exact capitalization and spacing from the query

## Examples

Query: "Show me contracts with 株式会社ABC"
Response:
- company_names: ["株式会社ABC"]
- reasoning: "Extracted one Japanese company name"

Query: "Find contracts for ABC Corporation or XYZ Ltd"
Response:
- company_names: ["ABC Corporation", "XYZ Ltd"]
- reasoning: "Extracted two company names connected by 'or'"

Query: "Contracts ending in 2024"
Response:
- company_names: []
- reasoning: "No company names mentioned in the query"

Query: "Show me ABC Corp contracts"
Response:
- company_names: ["ABC Corp"]
- reasoning: "Extracted one company name with abbreviation"

Query: "List contracts with Google, Microsoft, and Amazon"
Response:
- company_names: ["Google", "Microsoft", "Amazon"]
- reasoning: "Extracted three company names from comma-separated list"

Query: "Contracts with the supplier"
Response:
- company_names: []
- reasoning: "Generic term 'supplier' is not a specific company name"

## User Query
{query}

Please extract all company names from the query above. If no company names are found, return an empty list.
"""


async def extract_company_names_from_query(query: str) -> List[str]:
    """
    Extract company names from a natural language query using LLM.

    Args:
        query: The user's natural language query

    Returns:
        List of company names found in the query (empty list if none found)

    Examples:
        >>> await extract_company_names_from_query("Show contracts with ABC Corp")
        ["ABC Corp"]

        >>> await extract_company_names_from_query("Contracts ending in 2024")
        []
    """
    if not query or not query.strip():
        logger.warning("Empty query provided for company name extraction")
        return []

    logger.info(f"Extracting company names from query: '{query}'")

    try:
        llm = LlamaSettings.llm

        prompt = COMPANY_NAME_EXTRACTION_PROMPT.format(query=query)

        sllm = llm.as_structured_llm(CompanyNameExtractionResponse)
        response = await sllm.acomplete(prompt)
        extraction_response: CompanyNameExtractionResponse = response.raw

        company_names = extraction_response.company_names or []

        if company_names:
            logger.info(
                f"Extracted {len(company_names)} company name(s): {company_names}. "
                f"Reasoning: {extraction_response.reasoning}"
            )
        else:
            logger.info(
                f"No company names extracted from query. "
                f"Reasoning: {extraction_response.reasoning}"
            )

        return company_names

    except Exception as e:
        logger.exception(f"Error extracting company names from query: {e}")
        # Return empty list on error - don't fail the entire query
        return []


async def extract_and_validate_company_names(
    query: str,
    available_companies: set[str],
) -> List[str]:
    """
    Extract company names from query and validate they exist in the database.

    This is a convenience function that combines extraction with validation.

    Args:
        query: The user's natural language query
        available_companies: Set of all available company names in the database

    Returns:
        List of extracted company names that exist in the database
    """
    extracted_names = await extract_company_names_from_query(query)

    if not extracted_names:
        return []

    # Validate that extracted names exist in the database (case-sensitive)
    validated_names = [name for name in extracted_names if name in available_companies]

    if len(validated_names) < len(extracted_names):
        missing = set(extracted_names) - set(validated_names)
        logger.info(
            f"Some extracted company names not found in database: {missing}. "
            f"These will be fuzzy-matched."
        )

    return validated_names
