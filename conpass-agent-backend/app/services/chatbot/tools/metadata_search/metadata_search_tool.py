from datetime import datetime
from typing import Set, Optional, Dict, Any, List
import copy
from app.core.config import settings
from app.core.logging_config import get_logger
from llama_index.core.tools import FunctionTool
from app.services.chatbot.tools.metadata_search.document_utils import (
    get_document_id,
)
from app.services.chatbot.tools.metadata_search.qdrant_client import (
    scroll_qdrant_with_filter,
)
from app.services.chatbot.tools.metadata_search.text_to_qdrant_filters import (
    convert_query_to_qdrant_filter,
)
from app.services.chatbot.tools.metadata_search.qdrant_filter import (
    QdrantFilterResponse,
)
from app.services.chatbot.tools.utils.document_store import get_metadata_from_docstore

logger = get_logger(__name__)

PAGE_SIZE = 20  # Fixed page size for pagination


def sanitize_filter_directory_ids(
    qdrant_filter: Dict[str, Any], authorized_directory_ids: List[int]
) -> Dict[str, Any]:
    """
    Sanitize a Qdrant filter to ensure it only contains authorized directory_ids.

    This prevents prompt injection attacks where an agent might try to pass
    unauthorized directory_ids in the filter_used parameter.

    Args:
        qdrant_filter: The Qdrant filter dictionary to sanitize
        authorized_directory_ids: List of directory IDs the user is authorized to access

    Returns:
        A sanitized filter with only authorized directory_ids
    """
    # Deep copy to avoid modifying the original
    sanitized_filter = copy.deepcopy(qdrant_filter)

    # Ensure "must" key exists
    if "must" not in sanitized_filter:
        sanitized_filter["must"] = []

    # Remove any existing directory_id filters from all clauses to prevent unauthorized access
    # Check "must" clause
    sanitized_filter["must"] = [
        condition
        for condition in sanitized_filter["must"]
        if not (isinstance(condition, dict) and condition.get("key") == "directory_id")
    ]

    # Check "should" clause if it exists
    if "should" in sanitized_filter and isinstance(sanitized_filter["should"], list):
        sanitized_filter["should"] = [
            condition
            for condition in sanitized_filter["should"]
            if not (
                isinstance(condition, dict) and condition.get("key") == "directory_id"
            )
        ]

    # Check "must_not" clause if it exists
    if "must_not" in sanitized_filter and isinstance(
        sanitized_filter["must_not"], list
    ):
        sanitized_filter["must_not"] = [
            condition
            for condition in sanitized_filter["must_not"]
            if not (
                isinstance(condition, dict) and condition.get("key") == "directory_id"
            )
        ]

    # Add the authorized directory_id filter to "must" clause
    # Use the same format as text_to_qdrant_filters.py
    if len(authorized_directory_ids) == 1:
        sanitized_filter["must"].append(
            {
                "key": "directory_id",
                "match": {"value": authorized_directory_ids[0]},
            }
        )
    else:
        sanitized_filter["must"].append(
            {
                "key": "directory_id",
                "match": {"any": authorized_directory_ids},
            }
        )

    logger.info(
        f"Sanitized filter: removed unauthorized directory_ids, "
        f"enforced authorized directory_ids: {authorized_directory_ids}"
    )

    return sanitized_filter


async def metadata_search(
    directory_ids: List[int],
    query: str,
    page: Optional[int] = None,
    filter_used: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    logger.info(
        f"metadata_search_tool called with directory_ids: {directory_ids}, query: {query}, page: {page}"
    )

    logger.info(f"agent_filter_used: {filter_used}")
    try:
        # Set default page (1-indexed)
        if page is None:
            page = 1
        elif page < 1:
            page = 1

        page_size = PAGE_SIZE
        # Convert page number to offset (page 1 = offset 0, page 2 = offset 20, etc.)
        offset = (page - 1) * page_size

        is_pagination = filter_used is not None and page > 1

        # Use provided filter only for pagination; otherwise generate a fresh one
        if is_pagination:
            logger.info("Reusing provided filter for pagination consistency")
            if not isinstance(filter_used, dict):
                return {
                    "success": False,
                    "error": "Invalid filter_used parameter: must be a dictionary",
                    "query": query,
                }
            qdrant_filter = sanitize_filter_directory_ids(filter_used, directory_ids)
            filter_response = QdrantFilterResponse(
                filter=None,
                reasoning="Filter reused from previous page for consistency",
            )
            qdrant_filter_res = (filter_response, qdrant_filter)
        else:
            logger.info("No prior filter to reuse; generating a new filter")
            qdrant_filter_res = await convert_query_to_qdrant_filter(
                query, directory_ids
            )

        if not qdrant_filter_res:
            return {
                "success": False,
                "error": "An error occurred while converting the query to filters",
                "query": query,
            }

        filter_response, qdrant_filter = qdrant_filter_res

        # Check if no valid filter was generated (LLM couldn't create filter)
        if qdrant_filter is None:
            return {
                "success": False,
                "error": "Cannot create a valid filter for this query based on available metadata fields",
                "query": query,
                "filter_reasoning": filter_response.reasoning
                if filter_response
                else None,
                "message": "The query cannot be filtered using the available metadata fields. This query should use semantic_search (vector search) instead to search within contract content. Available metadata fields are: company names, dates, contract types, auto-renewal status, court, etc. For queries about information not in metadata (like person names, specific clauses, contract text), use semantic_search tool.",
                "suggested_tool": "semantic_search",
            }

        collection_name = settings.QDRANT_COLLECTION
        if not collection_name:
            return {
                "success": False,
                "error": "QDRANT_COLLECTION not configured",
                "query": query,
            }

        initial_results = await scroll_qdrant_with_filter(
            collection_name=collection_name,
            qdrant_filter=qdrant_filter,
        )

        if not initial_results:
            return {
                "success": False,
                "query": query,
                "filter_reasoning": filter_response.reasoning,
                "filter_used": qdrant_filter,
                "message": "No contracts found matching the query",
            }

        unique_doc_ids: Set[int] = set()
        for result in initial_results:
            payload = result.get("payload", {})
            doc_id = get_document_id(payload)
            if doc_id:
                unique_doc_ids.add(doc_id)

        unique_doc_ids_list = list(unique_doc_ids)

        unique_contracts_count = len(unique_doc_ids_list)

        # Calculate total pages
        total_pages = (
            unique_contracts_count + page_size - 1
        ) // page_size  # Ceiling division

        # Apply pagination
        start_idx = offset
        end_idx = offset + page_size
        paginated_doc_ids = unique_doc_ids_list[start_idx:end_idx]
        has_more = end_idx < unique_contracts_count
        next_page = page + 1 if has_more else None

        logger.info(
            f"Processing {len(paginated_doc_ids)} of {unique_contracts_count} contracts (page: {page}/{total_pages}, page_size: {page_size})"
        )

        documents = {}

        for doc_id in paginated_doc_ids:
            doc_data = await get_metadata_from_docstore(directory_ids, doc_id)
            if doc_data:
                documents[doc_id] = doc_data
            else:
                logger.warning(f"Document {doc_id} not found in docstore")

        if not documents:
            return {
                "success": False,
                "query": query,
                "filter_reasoning": filter_response.reasoning,
                "filter_used": qdrant_filter,
                "message": f"Found {len(paginated_doc_ids)} document ID(s) but none were available in docstore",
            }

        # Build structured contracts list
        contracts: List[Dict[str, Any]] = []

        for doc_id, doc_data in documents.items():
            metadata = doc_data["metadata"]

            contract_data: Dict[str, Any] = {
                "contract_id": doc_id,
                "metadata": {
                    "title": metadata.get("契約書名_title"),
                    "company_a": metadata.get("会社名_甲_company_a"),
                    "company_b": metadata.get("会社名_乙_company_b"),
                    "company_c": metadata.get("会社名_丙_company_c"),
                    "company_d": metadata.get("会社名_丁_company_d"),
                    "contract_type": metadata.get("契約種別_contract_type"),
                    "contract_date": metadata.get("契約日_contract_date"),
                    "contract_start_date": metadata.get(
                        "契約開始日_contract_start_date"
                    ),
                    "contract_end_date": metadata.get("契約終了日_contract_end_date"),
                    "auto_update": metadata.get("自動更新の有無_auto_update"),
                    "cancel_notice_date": metadata.get("契約終了日_cancel_notice_date"),
                    "court": metadata.get("裁判所_court"),
                },
                "url": f"{settings.CONPASS_FRONTEND_BASE_URL}/contract/{doc_id}",
            }

            contracts.append(contract_data)

        response: Dict[str, Any] = {
            "success": True,
            "query": query,
            "filter_reasoning": filter_response.reasoning,
            "filter_used": qdrant_filter,
            "contracts": contracts,
            "contracts_found": unique_contracts_count,
            "contracts_shown": len(contracts),
            "pagination": {
                "page_size": page_size,
                "current_page": page,
                "total_pages": total_pages,
                "has_more": has_more,
                "next_page": next_page,
            },
        }

        return response

    except Exception as e:
        logger.exception(f"Error fetching contracts: {e}")
        return {
            "success": False,
            "error": str(e),
            "query": query,
            "message": "An unexpected error occurred while fetching contracts",
        }


def get_metadata_search_tool(directory_ids: List[int]) -> FunctionTool:
    today = datetime.now().strftime("%Y-%m-%d")

    return FunctionTool.from_defaults(
        async_fn=metadata_search,
        name="metadata_search_tool",
        description=f"""
        Today's date is {today}.

        Primary tool to list or find contracts by **metadata only** (NOT contract content/text). Use it when the request can be answered with the available metadata fields.

        Use this tool when
        - User wants to filter/find contracts by company names, dates, contract attributes
        - Query can be answered using ONLY metadata fields (no need to read contract text)
        - Keywords: "show", "list", "find contracts with [company/date/type]"

        Do NOT use this tool when
        - Query asks about contract CONTENT (clauses, terms, obligations, definitions) → use semantic_search instead
        - Query mentions person names, specific clause types, or any text NOT in metadata → use semantic_search instead
        - User specifies a CONTRACT ID and wants details FROM that contract → use read_contracts_tool instead

        Available metadata fields
        - contract_id
        - title
        - company_a, company_b, company_c, company_d (company names only - not person names)
        - contract_type
        - contract_date, contract_start_date, contract_end_date
        - auto_update
        - cancel_notice_date
        - court

        Critical routing examples
        - "List contracts with 株式会社ABC" → metadata_search ✓ (company in metadata)
        - "Contracts ending in 2024" → metadata_search ✓ (date in metadata)
        - "Which contracts mention John Smith?" → semantic_search ✓ (person name NOT in metadata)
        - "Find contracts with SLA clauses" → semantic_search ✓ (clause content NOT in metadata)
        - "What are the SLA terms in contract 4824?" → read_contracts_tool ✓ (specific contract ID)

        Calling guidance
        - query: Use the user's exact question as the query parameter. Only modify or add context when: (1) the user explicitly references previous results (e.g., "those contracts", "the previous search"), (2) minimal context is absolutely necessary to understand what the user is asking (e.g., if user says "that contract" without context), or (3) the question is incomplete and cannot be understood without conversation history. For pagination commands (e.g., "next", "more", "show more", "次のページ", "もっと見る"), reuse the ORIGINAL query from the previous metadata_search call, along with the filter_used from that previous call. Do NOT rephrase or "improve" the user's wording unless context is needed.
        - page: 1-indexed page number. Omit for the first page; use pagination.next_page for later pages. When user requests pagination (e.g., "next", "more"), use the next_page value from the previous metadata_search response.
        - filter_used: reuse exactly the filter from a previous metadata_search response when: (1) the user explicitly requests more results/pagination (e.g., "next", "more", "show more"), OR (2) the user references previous results. Always reuse filter_used when paginating. Do not reuse when the user starts a new search.

        Response fields
        - success (bool), query (str), filter_reasoning (str), filter_used (dict)
        - contracts: each has contract_id, metadata (title/companies/dates/auto_update/court/etc.), url
        - contracts_found, contracts_shown
        - pagination: page_size (20), current_page, total_pages, has_more, next_page
        
        CRITICAL - URL Handling
        - Each contract includes a "url" field with the valid URL to view that contract
        - NEVER fabricate or make up URLs - ONLY use the URLs provided in the tool response
        - If displaying contracts, always include the URL from the response data

        Pagination reminders
        - Results are capped at 20 per page.
        - When has_more is True and the user asks for more, call again with the SAME query, page=pagination.next_page, and the SAME filter_used from the first call.
        - If the user changes the request, start a new search without filter_used.
        """,
        partial_params={"directory_ids": directory_ids},
    )
