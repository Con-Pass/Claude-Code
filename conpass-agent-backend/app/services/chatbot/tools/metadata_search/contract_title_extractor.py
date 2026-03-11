"""
Contract title extraction service using LLM.
Extracts contract title(s) from natural language queries for fuzzy matching.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from llama_index.core.settings import Settings as LlamaSettings

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class ContractTitleExtractionResponse(BaseModel):
    """Response schema for contract title extraction."""

    titles: List[str] = Field(
        default_factory=list,
        description="List of contract titles or title search phrases found in the query. Empty list if none found.",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Brief explanation of what title(s) were identified and why.",
    )


CONTRACT_TITLE_EXTRACTION_PROMPT = """
You are an expert at extracting contract title search terms from natural language queries.

Your task is to identify when the user is searching by contract title (契約書名) and extract the exact title or phrase they are looking for.

## Guidelines

1. **Extract title search terms** - When the user asks for contracts by title (e.g. "契約書名が〇〇の契約", "title containing X", "雇用契約書を探して"), extract the title or phrase they want to match.
2. **Preserve the exact text** - Use the user's wording; do not translate or paraphrase (e.g. keep "雇用契約書" as-is if that is what they said).
3. **Single phrase per query** - If the user clearly asks for one title, return one item. If they list multiple titles (e.g. "雇用契約書 or 業務委託契約書"), return multiple.
4. **No generic queries** - If the user is not searching by contract title (e.g. only by company, date, or "all contracts"), return an empty list.
5. **Japanese and English** - Handle both Japanese (雇用契約書, 秘密保持契約書) and English (employment contract, NDA) title references.

## Examples

Query: "契約書名が雇用契約書の契約を探して"
Response:
- titles: ["雇用契約書"]
- reasoning: "User is searching for contracts with title 雇用契約書"

Query: "title is 業務委託契約書"
Response:
- titles: ["業務委託契約書"]
- reasoning: "User specified contract title 業務委託契約書"

Query: "Show me contracts with 秘密保持契約書 in the title"
Response:
- titles: ["秘密保持契約書"]
- reasoning: "User wants contracts whose title contains 秘密保持契約書"

Query: "Contracts with 株式会社ABC"
Response:
- titles: []
- reasoning: "User is searching by company name, not by contract title"

Query: "Contracts ending in 2024"
Response:
- titles: []
- reasoning: "User is searching by date only, no title mentioned"

Query: "雇用契約書 or 請負契約書"
Response:
- titles: ["雇用契約書", "請負契約書"]
- reasoning: "User is searching for either of two contract types/titles"

## User Query
{query}

Extract contract title search term(s) from the query above. If the user is not searching by contract title, return an empty list.
"""


async def extract_contract_titles_from_query(query: str) -> List[str]:
    """
    Extract contract title search terms from a natural language query using LLM.

    Args:
        query: The user's natural language query

    Returns:
        List of title phrases to search for (empty list if none found)
    """
    if not query or not query.strip():
        logger.warning("Empty query provided for contract title extraction")
        return []

    logger.info(f"Extracting contract titles from query: '{query}'")

    try:
        llm = LlamaSettings.llm

        prompt = CONTRACT_TITLE_EXTRACTION_PROMPT.format(query=query)
        sllm = llm.as_structured_llm(ContractTitleExtractionResponse)
        response = await sllm.acomplete(prompt)
        extraction_response: ContractTitleExtractionResponse = response.raw

        titles = extraction_response.titles or []

        if titles:
            logger.info(
                f"Extracted {len(titles)} contract title(s): {titles}. "
                f"Reasoning: {extraction_response.reasoning}"
            )
        else:
            logger.info(
                f"No contract titles extracted from query. "
                f"Reasoning: {extraction_response.reasoning}"
            )

        return titles

    except Exception as e:
        logger.exception(f"Error extracting contract titles from query: {e}")
        return []
