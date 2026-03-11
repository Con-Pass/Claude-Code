"""
Unified query metadata extraction using a single LLM call.
Extracts both company names and contract title search terms from natural language queries.
"""

from typing import List, Optional, Tuple
from pydantic import BaseModel, Field

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class QueryMetadataExtractionResponse(BaseModel):
    """Response schema for unified company + title extraction."""

    company_names: List[str] = Field(
        default_factory=list,
        description="List of company names found in the query. Empty list if none found.",
    )
    contract_titles: List[str] = Field(
        default_factory=list,
        description="List of contract title search phrases (契約書名) found in the query. Empty list if none found.",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Brief explanation of what was identified.",
    )


QUERY_METADATA_EXTRACTION_PROMPT = """
You are an expert at extracting search metadata from natural language queries about contracts.

Your task is to analyze the user's query and extract TWO types of information in a single pass:

1. **Company names** - Any specific company/organization names the user is searching for (e.g. 株式会社ABC, ABC Corp). Do NOT include generic terms like "supplier" or "client".
2. **Contract title search terms** - When the user is searching by contract title/契約書名 (e.g. "契約書名が雇用契約書の契約", "title containing 秘密保持契約書", "雇用契約書を探して"), extract the exact title or phrase they want to match.

## Guidelines

**Company names:**
- Extract exactly as written; preserve original text and formatting.
- Include all companies if multiple are mentioned (e.g. "Google, Microsoft, and Amazon" → all three).
- Japanese and English: 株式会社ABC, ABC Corp, etc.
- Empty list if the query has no specific company names.

**Contract titles:**
- Only extract when the user is clearly searching BY contract title (契約書名).
- Preserve the user's wording (e.g. keep "雇用契約書" or "秘密保持契約書" as-is).
- If user asks for one title, return one item; if they list multiple (e.g. "雇用契約書 or 請負契約書"), return multiple.
- Empty list if the user is not searching by title (e.g. only by company, date, or "all contracts").

## Examples

Query: "Show me contracts with 株式会社ABC"
- company_names: ["株式会社ABC"]
- contract_titles: []
- reasoning: "User searching by company only"

Query: "契約書名が雇用契約書の契約を探して"
- company_names: []
- contract_titles: ["雇用契約書"]
- reasoning: "User searching by contract title only"

Query: "Contracts with 株式会社ABC that are 業務委託契約書"
- company_names: ["株式会社ABC"]
- contract_titles: ["業務委託契約書"]
- reasoning: "User searching by both company and contract title"

Query: "Find contracts for ABC Corp or XYZ Ltd"
- company_names: ["ABC Corp", "XYZ Ltd"]
- contract_titles: []
- reasoning: "Two companies, no title filter"

Query: "Contracts ending in 2024"
- company_names: []
- contract_titles: []
- reasoning: "Date-only query, no company or title"

Query: "雇用契約書 or 請負契約書"
- company_names: []
- contract_titles: ["雇用契約書", "請負契約書"]
- reasoning: "User searching by two contract titles"

Query: "Show me 秘密保持契約書 with Google"
- company_names: ["Google"]
- contract_titles: ["秘密保持契約書"]
- reasoning: "Company and title both specified"

## User Query
{query}

Extract company_names and contract_titles from the query above. Use empty lists for any category that does not apply.
"""


async def extract_query_metadata(query: str) -> Tuple[List[str], List[str]]:
    """
    Extract company names and contract title search terms from a query in a single LLM call.

    Args:
        query: The user's natural language query

    Returns:
        Tuple of (company_names, contract_titles), each a list of strings (possibly empty)
    """
    if not query or not query.strip():
        logger.warning("Empty query provided for metadata extraction")
        return [], []

    logger.info(f"Extracting query metadata (companies + titles) from: '{query}'")

    try:
        from llama_index.core.settings import Settings
        llm = Settings.llm

        prompt = QUERY_METADATA_EXTRACTION_PROMPT.format(query=query)
        sllm = llm.as_structured_llm(QueryMetadataExtractionResponse)
        response = await sllm.acomplete(prompt)
        extraction: QueryMetadataExtractionResponse = response.raw

        company_names = extraction.company_names or []
        contract_titles = extraction.contract_titles or []

        logger.info(
            f"Extracted: company_names={company_names}, contract_titles={contract_titles}. "
            f"Reasoning: {extraction.reasoning}"
        )

        return company_names, contract_titles

    except Exception as e:
        logger.exception(f"Error in unified query metadata extraction: {e}")
        return [], []
