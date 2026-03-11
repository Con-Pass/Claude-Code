from typing import Tuple, Optional, List, Dict, Any, Set
from datetime import datetime
import json

from llama_index.llms.google_genai import GoogleGenAI
# from llama_index.llms.openai import OpenAI


from app.services.chatbot.tools.metadata_search.qdrant_filter import (
    QdrantFilterResponse,
    FilterValidationResponse,
)
from app.services.chatbot.tools.metadata_search.prompts import (
    TEXT_TO_QDRANT_FILTER_PROMPT_TEMPLATE,
    FILTER_VALIDATION_PROMPT_TEMPLATE,
)
from app.services.chatbot.tools.metadata_search.filter_converter import (
    convert_filter_to_dict,
)
from app.services.chatbot.tools.metadata_search.query_metadata_extractor import (
    extract_query_metadata,
)
from app.services.chatbot.tools.metadata_search.fuzzy_company_matcher import (
    find_similar_company_names,
    find_similar_company_names_with_scores,
    normalize_company_name,
)
from app.services.chatbot.tools.metadata_search.company_name_cache import (
    get_company_names,
)
from app.services.chatbot.tools.metadata_search.qdrant_client import (
    scroll_qdrant_with_filter,
)
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


async def _fetch_company_names_from_qdrant(
    directory_ids: List[int],
) -> Set[str]:
    """
    Fetch all unique company names from Qdrant for the given directory IDs.

    Args:
        directory_ids: List of directory IDs to fetch company names from

    Returns:
        Set of unique company names (non-empty strings only)
    """
    logger.info(
        f"Fetching company names from Qdrant for directory_ids: {directory_ids}"
    )

    collection_name = settings.QDRANT_COLLECTION
    if not collection_name:
        logger.error("QDRANT_COLLECTION not configured")
        return set()

    # Build filter for directory_ids
    qdrant_filter = {
        "must": [
            {
                "key": "directory_id",
                # Always use "any" with a list for consistent typing
                "match": {
                    "any": directory_ids
                    if len(directory_ids) > 1
                    else [directory_ids[0]]
                },
            }
        ]
    }

    try:
        # Scroll all points with the filter
        results = await scroll_qdrant_with_filter(
            collection_name=collection_name,
            qdrant_filter=qdrant_filter,
        )

        # Extract unique company names from all company fields
        company_names: Set[str] = set()
        company_fields = [
            "会社名_甲_company_a",
            "会社名_乙_company_b",
            "会社名_丙_company_c",
            "会社名_丁_company_d",
        ]

        for result in results:
            payload = result.get("payload", {})
            for field in company_fields:
                company_name = payload.get(field)
                # Only add non-empty, non-null company names
                if (
                    company_name
                    and isinstance(company_name, str)
                    and company_name.strip()
                ):
                    company_names.add(company_name.strip())

        logger.info(f"Fetched {len(company_names)} unique company names from Qdrant")
        return company_names

    except Exception as e:
        logger.exception(f"Error fetching company names from Qdrant: {e}")
        return set()


async def _fetch_contract_titles_from_qdrant(
    directory_ids: List[int],
) -> Set[str]:
    """
    Fetch all unique contract titles (契約書名_title) from Qdrant for the given directory IDs.

    Args:
        directory_ids: List of directory IDs to fetch titles from

    Returns:
        Set of unique contract titles (non-empty strings only)
    """
    logger.info(
        f"Fetching contract titles from Qdrant for directory_ids: {directory_ids}"
    )

    collection_name = settings.QDRANT_COLLECTION
    if not collection_name:
        logger.error("QDRANT_COLLECTION not configured")
        return set()

    qdrant_filter = {
        "must": [
            {
                "key": "directory_id",
                "match": {
                    "any": directory_ids
                    if len(directory_ids) > 1
                    else [directory_ids[0]]
                },
            }
        ]
    }

    try:
        results = await scroll_qdrant_with_filter(
            collection_name=collection_name,
            qdrant_filter=qdrant_filter,
        )

        titles: Set[str] = set()
        title_field = "契約書名_title"

        for result in results:
            payload = result.get("payload", {})
            title = payload.get(title_field)
            if title and isinstance(title, str) and title.strip():
                titles.add(title.strip())

        logger.info(f"Fetched {len(titles)} unique contract titles from Qdrant")
        return titles

    except Exception as e:
        logger.exception(f"Error fetching contract titles from Qdrant: {e}")
        return set()


def _clean_filter_dict(filter_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively clean a filter dictionary by removing all None values.
    This is a safety net in case the LLM generates filters with null values.
    """
    if not isinstance(filter_dict, dict):
        return filter_dict

    cleaned = {}
    for key, value in filter_dict.items():
        if value is None:
            # Skip None values entirely
            continue
        elif isinstance(value, dict):
            # Recursively clean nested dicts
            cleaned_value = _clean_filter_dict(value)
            if cleaned_value:  # Only add if not empty after cleaning
                cleaned[key] = cleaned_value
        elif isinstance(value, list):
            # Clean each item in the list
            cleaned_list = []
            for item in value:
                if isinstance(item, dict):
                    cleaned_item = _clean_filter_dict(item)
                    if cleaned_item:  # Only add if not empty after cleaning
                        cleaned_list.append(cleaned_item)
                elif item is not None:
                    cleaned_list.append(item)
            if cleaned_list:  # Only add if not empty after cleaning
                cleaned[key] = cleaned_list
        else:
            # Keep other values as-is
            cleaned[key] = value

    return cleaned


def _validate_filter_structure(
    filter_dict: Dict[str, Any],
) -> Tuple[bool, Optional[str]]:
    """
    Validate that the filter dictionary structure is correct.
    Checks for malformed JSON, duplicate keys, and invalid structures.
    """
    try:
        # Try to serialize and deserialize to check for JSON validity
        json_str = json.dumps(filter_dict)
        parsed = json.loads(json_str)

        # Check for duplicate keys in the structure
        def check_duplicates(obj, path="root"):
            if isinstance(obj, dict):
                keys = list(obj.keys())
                if len(keys) != len(set(keys)):
                    return False, f"Duplicate keys found at {path}: {keys}"
                for key, value in obj.items():
                    is_valid, error = check_duplicates(value, f"{path}.{key}")
                    if not is_valid:
                        return False, error
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    is_valid, error = check_duplicates(item, f"{path}[{i}]")
                    if not is_valid:
                        return False, error
            return True, None

        is_valid, error = check_duplicates(parsed)
        if not is_valid:
            return False, error

        # Check for malformed field conditions
        def validate_range_condition(
            condition: Dict[str, Any],
        ) -> Tuple[bool, Optional[str]]:
            # A FieldCondition should have either match OR range, not both
            # Check if both keys exist (even if one is null)
            has_match = "match" in condition
            has_range = "range" in condition

            if has_match and has_range:
                return (
                    False,
                    f"FieldCondition cannot have both 'match' and 'range' keys on field '{condition.get('key', 'unknown')}'. "
                    f"A FieldCondition should contain ONLY 'match' OR ONLY 'range', not both. "
                    f"Even if one is null (like 'range': null), having both keys is incorrect. "
                    f"SOLUTION: Remove the unused key entirely from the JSON. "
                    f"If you need to filter by both contract_id and date, create TWO separate FieldCondition objects in the 'must' array.",
                )

            if "range" in condition and isinstance(condition["range"], dict):
                range_dict = condition["range"]

                # gt and gte should never be used together
                if "gt" in range_dict and "gte" in range_dict:
                    return (
                        False,
                        f"Range condition cannot have both 'gt' ({range_dict.get('gt')}) and 'gte' ({range_dict.get('gte')}) together. "
                        f"Use only one: 'gt' for strict greater than, or 'gte' for greater than or equal.",
                    )

                # lt and lte should never be used together
                if "lt" in range_dict and "lte" in range_dict:
                    return (
                        False,
                        f"Range condition cannot have both 'lt' ({range_dict.get('lt')}) and 'lte' ({range_dict.get('lte')}) together. "
                        f"Use only one: 'lt' for strict less than, or 'lte' for less than or equal.",
                    )
            return True, None

        def validate_conditions(
            conditions: List[Any], path: str
        ) -> Tuple[bool, Optional[str]]:
            for i, condition in enumerate(conditions):
                if isinstance(condition, dict):
                    # Check if it's a FieldCondition
                    if "key" in condition:
                        is_valid, error = validate_range_condition(condition)
                        if not is_valid:
                            return False, f"{path}[{i}]: {error}"
                    # Check if it's a nested Filter
                    if (
                        "must" in condition
                        or "should" in condition
                        or "must_not" in condition
                    ):
                        if "must" in condition and condition["must"]:
                            is_valid, error = validate_conditions(
                                condition["must"], f"{path}[{i}].must"
                            )
                            if not is_valid:
                                return False, error
                        if "should" in condition and condition["should"]:
                            is_valid, error = validate_conditions(
                                condition["should"], f"{path}[{i}].should"
                            )
                            if not is_valid:
                                return False, error
                        if "must_not" in condition and condition["must_not"]:
                            is_valid, error = validate_conditions(
                                condition["must_not"], f"{path}[{i}].must_not"
                            )
                            if not is_valid:
                                return False, error
            return True, None

        # Validate all clauses
        if "must" in parsed and parsed["must"]:
            is_valid, error = validate_conditions(parsed["must"], "must")
            if not is_valid:
                return False, error
        if "should" in parsed and parsed["should"]:
            is_valid, error = validate_conditions(parsed["should"], "should")
            if not is_valid:
                return False, error
        if "must_not" in parsed and parsed["must_not"]:
            is_valid, error = validate_conditions(parsed["must_not"], "must_not")
            if not is_valid:
                return False, error

        return True, None
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        return False, f"Invalid JSON structure: {str(e)}"
    except Exception as e:
        return False, f"Structure validation error: {str(e)}"


async def _validate_filter(
    query: str,
    filter_response: QdrantFilterResponse,
    previous_reasoning: Optional[str] = None,
    previous_feedback: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """Validate if the generated filter is correct."""
    try:
        # Gemini implementation (commented out)
        llm = GoogleGenAI(
            model="gemini-2.5-flash",
            temperature=0.0,  # Use 0 for maximum consistency and determinism
            api_key=settings.GOOGLE_AI_API_KEY,
        )

        # GPT-4.1 implementation
        # llm = OpenAI(
        #     model="gpt-4.1",
        #     temperature=0.0,  # Use 0 for maximum consistency and determinism
        #     api_key=settings.OPENAI_API_KEY,
        #     timeout=30,
        #     max_retries=2,
        # )

        # Use exclude_none=True to prevent null fields from being sent to validator
        filter_json = filter_response.model_dump_json(indent=2, exclude_none=True)
        prompt = FILTER_VALIDATION_PROMPT_TEMPLATE.format(
            query=query,
            filter_json=filter_json,
            previous_reasoning=previous_reasoning or "N/A (first attempt)",
            previous_feedback=previous_feedback or "N/A (first attempt)",
        )

        sllm = llm.as_structured_llm(FilterValidationResponse)
        response = await sllm.acomplete(prompt)
        validation_response: FilterValidationResponse = response.raw

        logger.info(
            f"Filter validation result: is_correct={validation_response.is_correct}, "
            f"feedback={validation_response.feedback}"
        )

        return validation_response.is_correct, validation_response.feedback
    except Exception as e:
        logger.error(f"Error validating filter: {e}")
        # On validation error, assume incorrect to trigger retry
        return False, f"Validation error: {str(e)}"


async def _generate_filter(
    query: str,
    previous_reasoning: Optional[str] = None,
    previous_feedback: Optional[str] = None,
    company_matches: Optional[Dict[str, List[str]]] = None,
    title_matches: Optional[Dict[str, List[str]]] = None,
) -> QdrantFilterResponse:
    """Generate a filter from the query, optionally with retry context."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Build prompt with retry context if available
    base_prompt = TEXT_TO_QDRANT_FILTER_PROMPT_TEMPLATE.format(today=today, query=query)

    # Add fuzzy company matching context if available
    if company_matches:
        fuzzy_context = "\n\n## Fuzzy Company Name Matching Results\n\n"
        fuzzy_context += "The following company names were extracted from the query and matched to actual company names in the database:\n\n"

        for extracted, matched_list in company_matches.items():
            if len(matched_list) == 1 and matched_list[0] == extracted:
                # Exact match
                fuzzy_context += f"- **'{extracted}'**: Exact match found\n"
            else:
                # Fuzzy matches
                fuzzy_context += f"- **'{extracted}'**: Fuzzy matched to {len(matched_list)} company name(s):\n"
                for matched in matched_list:
                    fuzzy_context += f"  - {matched}\n"

        fuzzy_context += "\n**IMPORTANT**: When creating the filter, use the MATCHED company names (on the right side), NOT the original extracted names. "
        fuzzy_context += "If multiple matches are found for one extracted name, use `match.any` with all matched names.\n"

        base_prompt = base_prompt + fuzzy_context

    # Add fuzzy contract title matching context if available
    if title_matches:
        title_context = (
            "\n\n## Fuzzy Contract Title Matching Results (契約書名_title)\n\n"
        )
        title_context += "The following contract title search terms were extracted from the query and fuzzy-matched to actual titles in the database:\n\n"

        for extracted, matched_list in title_matches.items():
            if len(matched_list) == 1 and matched_list[0] == extracted:
                title_context += f"- **'{extracted}'**: Exact match found\n"
            else:
                title_context += f"- **'{extracted}'**: Fuzzy matched to {len(matched_list)} title(s):\n"
                for matched in matched_list:
                    title_context += f"  - {matched}\n"

        title_context += "\n**IMPORTANT**: When creating the filter, use field **契約書名_title** with the MATCHED titles (on the right side), NOT the original extracted phrase. "
        title_context += "Use `match.any` with the list of matched titles so that contracts with any of those titles are returned.\n"

        base_prompt = base_prompt + title_context

    if previous_reasoning or previous_feedback:
        retry_context = "\n\n## Previous Attempt Feedback\n"
        if previous_feedback:
            retry_context += f"**Validation Feedback**: {previous_feedback}\n"
        if previous_reasoning:
            retry_context += f"**Previous Reasoning**: {previous_reasoning}\n"
        retry_context += (
            "\nPlease fix the issues identified above and generate a correct filter."
        )
        prompt = base_prompt + retry_context
    else:
        prompt = base_prompt

    # Gemini implementation (commented out)
    llm = GoogleGenAI(
        model="gemini-2.5-flash",
        temperature=0.0,  # Use 0 for maximum consistency and determinism
        api_key=settings.GOOGLE_AI_API_KEY,
    )

    # GPT-4.1 implementation
    # llm = OpenAI(
    #     model="gpt-4.1",
    #     temperature=0.0,  # Use 0 for maximum consistency and determinism
    #     api_key=settings.OPENAI_API_KEY,
    #     timeout=30,
    #     max_retries=2,
    # )

    sllm = llm.as_structured_llm(QdrantFilterResponse)
    response = await sllm.acomplete(prompt)
    filter_response: QdrantFilterResponse = response.raw

    # Safety net: Clean the filter response to remove any None values that slipped through
    if filter_response.filter:
        try:
            # Convert to dict with exclude_none to get a clean representation
            filter_dict = filter_response.filter.model_dump(exclude_none=True)
            # Additional safety: recursively remove any remaining None values
            cleaned_filter_dict = _clean_filter_dict(filter_dict)
            # Reconstruct the filter from the cleaned dict
            from app.services.chatbot.tools.metadata_search.qdrant_filter import Filter

            filter_response.filter = Filter(**cleaned_filter_dict)
        except Exception as e:
            logger.warning(f"Error cleaning filter response: {e}")
            # Continue with original filter_response if cleaning fails

    # Validate the structure before logging
    try:
        # Use exclude_none=True to prevent null fields from appearing in JSON
        filter_json = filter_response.model_dump_json(indent=2, exclude_none=True)
        logger.info(f"LLM Response: {filter_json}")

        # Try to parse the JSON to ensure it's valid
        json.loads(filter_json)  # Validate JSON structure

        # Check if filter exists and validate its structure
        if filter_response.filter:
            # Use exclude_none=True to prevent validation issues with null fields
            filter_dict = filter_response.filter.model_dump(exclude_none=True)
            is_valid, error = _validate_filter_structure(filter_dict)
            if not is_valid:
                logger.error(f"Generated filter has structural issues: {error}")
                logger.error(f"Problematic filter structure: {filter_dict}")
    except json.JSONDecodeError as e:
        logger.error(f"Generated filter response is not valid JSON: {e}")
    except Exception as e:
        logger.warning(f"Error validating filter structure: {e}")

    return filter_response


async def _apply_fuzzy_company_matching(
    query: str,
    directory_ids: List[int],
    pre_extracted_companies: Optional[List[str]] = None,
) -> Tuple[str, Optional[Dict[str, List[str]]]]:
    """
    Apply fuzzy matching to company names in the query.

    This function:
    1. Uses the pre-extracted company names (from extract_query_metadata)
    2. Fetches all available company names from Qdrant
    3. Performs fuzzy matching to find similar company names
    4. Returns an enhanced query with matched company names

    Args:
        query: The original user query
        directory_ids: List of directory IDs to fetch company names from
        pre_extracted_companies: List of company names from extract_query_metadata (can be empty)

    Returns:
        Tuple of (enhanced_query, company_matches_dict)
        - enhanced_query: Original query or enhanced with fuzzy match info
        - company_matches_dict: Dict mapping extracted names to matched names
    """
    try:
        extracted_companies = pre_extracted_companies or []

        if not extracted_companies:
            logger.info(
                "No company names extracted from query, skipping fuzzy matching"
            )
            return query, None

        logger.info(f"Extracted company names from query: {extracted_companies}")

        # Fetch company names using cache (24h TTL, per-directory isolation)
        available_companies = await get_company_names(directory_ids)

        if not available_companies:
            logger.warning("No company names available in database for fuzzy matching")
            return query, None

        logger.info(
            f"Fetched {len(available_companies)} unique company names from database"
        )

        # Step 3: Perform fuzzy matching for each extracted company
        company_matches: Dict[str, List[str]] = {}

        for extracted_name in extracted_companies:
            # Check for exact match first
            if extracted_name in available_companies:
                logger.info(f"✓ Exact match: '{extracted_name}'")
                company_matches[extracted_name] = [extracted_name]
                continue

            # Check for normalized semantic match
            # This catches cases like "euro finance" vs "EuroFinance AG"
            normalized_query = (
                normalize_company_name(extracted_name).lower().replace(" ", "")
            )

            semantic_match = None
            for company in available_companies:
                normalized_company = (
                    normalize_company_name(company).lower().replace(" ", "")
                )
                if normalized_query == normalized_company:
                    logger.info(f"✓ Semantic match: '{extracted_name}' → '{company}'")
                    semantic_match = company
                    break

            if semantic_match:
                company_matches[extracted_name] = [semantic_match]
                continue

            # Perform fuzzy matching with scores
            similar_names_with_scores = find_similar_company_names_with_scores(
                query_company=extracted_name,
                all_companies=available_companies,
                threshold=60,  # Lower threshold for initial matching
                max_matches=10,  # Get more matches to filter
            )

            # Filter out poor matches with intelligent rules
            filtered_matches = []
            query_words = set(extracted_name.lower().split())
            query_normalized = normalize_company_name(extracted_name).lower()

            for name, score in similar_names_with_scores:
                # Skip very short matches (likely false positives like "ney")
                if len(name.strip()) < 3:
                    logger.debug(
                        f"[{extracted_name}] Rejecting '{name}' (score: {score:.1f}) - too short"
                    )
                    continue

                # Check if normalized forms are very similar (handles "EuroFinance AG" case)
                name_normalized = normalize_company_name(name).lower()

                # If normalized names are very similar, accept even with lower score
                if query_normalized and name_normalized:
                    # Remove spaces for comparison
                    query_clean = query_normalized.replace(" ", "")
                    name_clean = name_normalized.replace(" ", "")

                    # Check if one contains the other or they're very similar
                    if (
                        query_clean in name_clean or name_clean in query_clean
                    ) and score >= 65:
                        logger.info(
                            f"[{extracted_name}] Accepting '{name}' (score: {score:.1f}) - normalized substring match"
                        )
                        filtered_matches.append((name, score))
                        continue

                # Standard threshold check
                if score < 70:
                    logger.debug(
                        f"[{extracted_name}] Rejecting '{name}' (score: {score:.1f}) - below 70 threshold"
                    )
                    continue

                # For multi-word queries, require at least one common word
                # This prevents "Xero" from matching "euro finance"
                if len(query_words) > 1:
                    match_words = set(name.lower().split())
                    common_words = query_words.intersection(match_words)
                    if not common_words:
                        logger.debug(
                            f"[{extracted_name}] Rejecting '{name}' (score: {score:.1f}) - no common words"
                        )
                        continue

                logger.info(
                    f"[{extracted_name}] Accepting '{name}' (score: {score:.1f}) - passed all filters"
                )
                filtered_matches.append((name, score))

            # Take top 3 filtered matches
            if filtered_matches:
                similar_names = [name for name, score in filtered_matches[:3]]
                scores_str = ", ".join(
                    [f"'{name}' ({score:.1f})" for name, score in filtered_matches[:3]]
                )
                logger.info(
                    f"✓ Fuzzy matched '{extracted_name}' → {len(similar_names)} match(es): {scores_str}"
                )
                company_matches[extracted_name] = similar_names
            else:
                logger.warning(
                    f"✗ No matches found for '{extracted_name}' after filtering "
                    f"(threshold: 70, candidates reviewed: {len(similar_names_with_scores)}, "
                    f"available companies: {len(available_companies)})"
                )
                # Keep the original name even if no matches found
                company_matches[extracted_name] = [extracted_name]

        # Create summary of all matches
        if company_matches:
            match_info_parts = []
            for extracted, matched in company_matches.items():
                if matched != [
                    extracted
                ]:  # Only show if fuzzy/semantic matching occurred
                    if len(matched) == 1:
                        match_info_parts.append(f"'{extracted}' → '{matched[0]}'")
                    else:
                        matched_str = ", ".join([f"'{m}'" for m in matched])
                        match_info_parts.append(f"'{extracted}' → [{matched_str}]")

            if match_info_parts:
                logger.info(
                    f"📋 Company matching summary: {len(company_matches)} name(s) processed, "
                    f"{len(match_info_parts)} matched - {'; '.join(match_info_parts)}"
                )

        return query, company_matches

    except Exception as e:
        logger.exception(f"Error during fuzzy company matching: {e}")
        # Return original query on error - don't fail the entire process
        return query, None


async def _apply_fuzzy_title_matching(
    query: str,
    directory_ids: List[int],
    pre_extracted_titles: Optional[List[str]] = None,
) -> Tuple[str, Optional[Dict[str, List[str]]]]:
    """
    Apply fuzzy matching to contract titles (契約書名_title) in the query.

    This function:
    1. Uses the pre-extracted title terms (from extract_query_metadata)
    2. Fetches all available contract titles from Qdrant
    3. Performs fuzzy matching to find similar titles
    4. Returns a dict mapping extracted phrases to matched titles for the filter prompt

    Args:
        query: The original user query
        directory_ids: List of directory IDs to fetch titles from
        pre_extracted_titles: List of title search terms from extract_query_metadata (can be empty)

    Returns:
        Tuple of (enhanced_query, title_matches_dict)
        - enhanced_query: Original query (unchanged)
        - title_matches_dict: Dict mapping extracted phrase to list of matched titles
    """
    try:
        extracted_titles = pre_extracted_titles or []

        if not extracted_titles:
            logger.info(
                "No contract titles extracted from query, skipping fuzzy title matching"
            )
            return query, None

        logger.info(
            f"Extracted contract title search terms from query: {extracted_titles}"
        )

        available_titles = await _fetch_contract_titles_from_qdrant(directory_ids)

        if not available_titles:
            logger.warning(
                "No contract titles available in database for fuzzy matching"
            )
            return query, None

        logger.info(
            f"Fetched {len(available_titles)} unique contract titles from database"
        )

        title_matches: Dict[str, List[str]] = {}

        for extracted in extracted_titles:
            if extracted in available_titles:
                logger.info(f"Exact title match found for '{extracted}'")
                title_matches[extracted] = [extracted]
                continue

            similar_titles = find_similar_company_names(
                query_company=extracted,
                all_companies=available_titles,
                threshold=70,
                max_matches=10,
            )

            if similar_titles:
                logger.info(f"Fuzzy matched title '{extracted}' to: {similar_titles}")
                title_matches[extracted] = similar_titles
            else:
                logger.warning(
                    f"No fuzzy matches found for title '{extracted}' "
                    f"(threshold=70, available titles={len(available_titles)})"
                )
                title_matches[extracted] = [extracted]

        return query, title_matches if title_matches else None

    except Exception as e:
        logger.exception(f"Error during fuzzy title matching: {e}")
        return query, None


async def convert_query_to_qdrant_filter(
    query: str,
    directory_ids: List[int],
) -> Tuple[QdrantFilterResponse, Optional[dict]] | None:
    logger.info(f"Converting query to Qdrant filter: {query}")
    try:
        # Single LLM call to extract both company names and contract title search terms
        extracted_companies, extracted_titles = await extract_query_metadata(query)
        # Apply fuzzy matching using the pre-extracted lists (no further LLM calls)
        enhanced_query, company_matches = await _apply_fuzzy_company_matching(
            query, directory_ids, pre_extracted_companies=extracted_companies
        )
        _, title_matches = await _apply_fuzzy_title_matching(
            query, directory_ids, pre_extracted_titles=extracted_titles
        )
        max_retries = 3
        previous_reasoning = None
        previous_feedback = None

        for attempt in range(1, max_retries + 1):
            logger.info(f"Filter generation attempt {attempt}/{max_retries}")

            # Generate filter (pass company_matches and title_matches for fuzzy matching context)
            filter_response = await _generate_filter(
                query,
                previous_reasoning,
                previous_feedback,
                company_matches,
                title_matches,
            )

            # Check if LLM returned null filter (cannot create valid filter)
            if filter_response.filter is None:
                logger.warning(
                    f"LLM could not generate a valid filter for query: {query}. "
                    f"Reasoning: {filter_response.reasoning}"
                )
                # Return filter_response with None qdrant_filter so we can access reasoning
                return filter_response, None

            # Validate the filter structure BEFORE LLM validation
            filter_dict = filter_response.filter.model_dump(exclude_none=True)
            is_valid, error = _validate_filter_structure(filter_dict)
            if not is_valid:
                logger.warning(
                    f"Filter structure validation failed on attempt {attempt}: {error}"
                )
                if attempt < max_retries:
                    previous_reasoning = filter_response.reasoning
                    previous_feedback = f"Filter structure validation failed: {error}"
                    logger.info(
                        f"Retrying filter generation (attempt {attempt + 1})..."
                    )
                    continue
                else:
                    logger.error(
                        f"Filter structure validation failed after {max_retries} attempts. "
                        f"Last error: {error}"
                    )
                    return filter_response, None

            # Validate the filter with LLM
            is_correct, feedback = await _validate_filter(
                query, filter_response, previous_reasoning, previous_feedback
            )

            if not is_correct:
                logger.warning(
                    f"Filter validation failed on attempt {attempt}: {feedback}"
                )
                if attempt < max_retries:
                    # Store context for retry
                    previous_reasoning = filter_response.reasoning
                    previous_feedback = feedback
                    logger.info(
                        f"Retrying filter generation (attempt {attempt + 1})..."
                    )
                    continue
                else:
                    logger.error(
                        f"Filter validation failed after {max_retries} attempts. "
                        f"Last feedback: {feedback}"
                    )
                    # Return the last attempt even if incorrect, so we can access reasoning
                    return filter_response, None

            logger.info(f"Filter validation passed on attempt {attempt}")

            # Convert filter to dict
            qdrant_filter = convert_filter_to_dict(filter_response)

            # If conversion resulted in None or empty filter, abort
            if qdrant_filter is None or not qdrant_filter:
                logger.warning(
                    f"Filter conversion resulted in empty filter for query: {query}. "
                    f"Reasoning: {filter_response.reasoning}"
                )
                if attempt < max_retries:
                    previous_reasoning = filter_response.reasoning
                    previous_feedback = "Filter conversion resulted in empty filter"
                    logger.info(
                        f"Retrying filter generation (attempt {attempt + 1})..."
                    )
                    continue
                else:
                    # Return filter_response with None qdrant_filter so we can access reasoning
                    return filter_response, None

            # Validate the converted filter structure
            is_valid, error = _validate_filter_structure(qdrant_filter)
            if not is_valid:
                logger.error(
                    f"Converted filter has structural issues: {error}. "
                    f"Filter: {qdrant_filter}"
                )
                if attempt < max_retries:
                    previous_reasoning = filter_response.reasoning
                    previous_feedback = f"Filter structure validation failed: {error}"
                    logger.info(
                        f"Retrying filter generation (attempt {attempt + 1})..."
                    )
                    continue
                else:
                    logger.error(
                        f"Filter structure validation failed after {max_retries} attempts. "
                        f"Last error: {error}"
                    )
                    return filter_response, None

            # Filter passed all validations, break out of retry loop
            break

        # Ensure "must" key exists
        if "must" not in qdrant_filter:
            qdrant_filter["must"] = []

        # Add directory_id filter (deduplicate directory_ids)
        unique_directory_ids = list(
            dict.fromkeys(directory_ids)
        )  # Preserves order while removing duplicates
        if len(unique_directory_ids) != len(directory_ids):
            logger.warning(
                f"Removed {len(directory_ids) - len(unique_directory_ids)} duplicate directory_ids. "
                f"Original count: {len(directory_ids)}, unique count: {len(unique_directory_ids)}"
            )
        qdrant_filter["must"].append(
            {
                "key": "directory_id",
                "match": {
                    "any": unique_directory_ids,
                },
            }
        )

        # Final validation after adding directory_id
        is_valid, error = _validate_filter_structure(qdrant_filter)
        if not is_valid:
            logger.error(
                f"Final filter has structural issues after adding directory_id: {error}. "
                f"Filter: {qdrant_filter}"
            )
            return filter_response, None

        logger.info(
            f"Qdrant filter dictionary: {json.dumps(qdrant_filter, indent=2, ensure_ascii=False)}"
        )
        return filter_response, qdrant_filter
    except Exception as e:
        logger.error(f"Error converting query to Qdrant filter: {e}")
        return None
