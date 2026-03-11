"""
Fuzzy company name matching service using rapidfuzz.
Handles variations, abbreviations, and typos in company name inputs.
"""

from typing import List, Tuple, Set
from rapidfuzz import process, fuzz

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Matching configuration
DEFAULT_THRESHOLD = 75  # Minimum similarity score (0-100)
MAX_MATCHES = 10  # Maximum number of matches to return
EXACT_MATCH_THRESHOLD = 95  # Score above which we consider it an exact match


def find_similar_company_names(
    query_company: str,
    all_companies: Set[str],
    threshold: int = DEFAULT_THRESHOLD,
    max_matches: int = MAX_MATCHES,
) -> List[str]:
    """
    Find company names similar to the query using fuzzy matching.

    Uses rapidfuzz's WRatio scorer which handles:
    - Case insensitivity
    - Partial matches
    - Token sorting (e.g., "ABC Corp" matches "Corp ABC")
    - Common abbreviations

    Args:
        query_company: The company name from the user query
        all_companies: Set of all available company names
        threshold: Minimum similarity score (0-100). Default 75.
        max_matches: Maximum number of matches to return. Default 10.

    Returns:
        List of matching company names, sorted by similarity (best first)

    Examples:
        >>> companies = {"ABC Corporation", "XYZ Ltd", "ABC Corp"}
        >>> find_similar_company_names("ABC Corp", companies)
        ["ABC Corp", "ABC Corporation"]
    """
    if not query_company or not query_company.strip():
        logger.warning("Empty query company name provided")
        return []

    if not all_companies:
        logger.warning("No company names available for matching")
        return []

    query_company = query_company.strip()

    logger.info(
        f"Fuzzy matching company name: '{query_company}' "
        f"against {len(all_companies)} companies (threshold={threshold})"
    )

    try:
        # First, check for direct exact string match (case-sensitive)
        if query_company in all_companies:
            logger.info(
                f"Found direct exact match for '{query_company}', "
                f"returning only this match and skipping fuzzy search"
            )
            return [query_company]

        # Use WRatio scorer combined with token_set_ratio for Japanese company names.
        # WRatio handles partial matches and token sorting.
        # token_set_ratio is better for word order differences (ABC株式会社 vs 株式会社ABC).
        matches_wratio = process.extract(
            query_company,
            all_companies,
            scorer=fuzz.WRatio,
            limit=max_matches,
            score_cutoff=threshold,
        )
        matches_tsr = process.extract(
            query_company,
            all_companies,
            scorer=fuzz.token_set_ratio,
            limit=max_matches,
            score_cutoff=threshold,
        )

        # Merge results: take best score per company
        score_map = {}
        for name, score, idx in matches_wratio:
            score_map[name] = max(score, score_map.get(name, 0))
        for name, score, idx in matches_tsr:
            score_map[name] = max(score, score_map.get(name, 0))

        # Sort by score descending and take top max_matches
        matches = sorted(
            [(name, score, 0) for name, score in score_map.items()],
            key=lambda x: -x[1],
        )[:max_matches]

        # Extract just the company names (matches are tuples of (name, score, index))
        matched_names = [match[0] for match in matches]

        # Check if there's an exact match (score >= EXACT_MATCH_THRESHOLD)
        if matches and matches[0][1] >= EXACT_MATCH_THRESHOLD:
            exact_match = matches[0][0]
            logger.info(
                f"Found exact match for '{query_company}': '{exact_match}' "
                f"(score: {matches[0][1]:.1f}), filtering out {len(matches) - 1} other fuzzy results"
            )
            return [exact_match]

        if matched_names:
            logger.info(
                f"Found {len(matched_names)} matches for '{query_company}': "
                f"{matched_names[:3]}{'...' if len(matched_names) > 3 else ''}"
            )
        else:
            logger.info(
                f"No matches found for '{query_company}' above threshold {threshold}"
            )

        return matched_names

    except Exception as e:
        logger.exception(f"Error during fuzzy matching: {e}")
        return []


def find_similar_company_names_with_scores(
    query_company: str,
    all_companies: Set[str],
    threshold: int = DEFAULT_THRESHOLD,
    max_matches: int = MAX_MATCHES,
) -> List[Tuple[str, float]]:
    """
    Find company names similar to the query with similarity scores.

    Same as find_similar_company_names but returns tuples of (name, score).

    Args:
        query_company: The company name from the user query
        all_companies: Set of all available company names
        threshold: Minimum similarity score (0-100). Default 75.
        max_matches: Maximum number of matches to return. Default 10.

    Returns:
        List of tuples (company_name, similarity_score), sorted by score (best first)

    Examples:
        >>> companies = {"ABC Corporation", "XYZ Ltd", "ABC Corp"}
        >>> find_similar_company_names_with_scores("ABC Corp", companies)
        [("ABC Corp", 100.0), ("ABC Corporation", 85.5)]
    """
    if not query_company or not query_company.strip():
        logger.warning("Empty query company name provided")
        return []

    if not all_companies:
        logger.warning("No company names available for matching")
        return []

    query_company = query_company.strip()

    try:
        # First, check for direct exact string match (case-sensitive)
        if query_company in all_companies:
            logger.info(
                f"Found direct exact match for '{query_company}', "
                f"returning only this match with score 100.0"
            )
            return [(query_company, 100.0)]

        matches = process.extract(
            query_company,
            all_companies,
            scorer=fuzz.WRatio,
            limit=max_matches,
            score_cutoff=threshold,
        )

        # Return tuples of (name, score)
        results = [(match[0], match[1]) for match in matches]

        if results:
            logger.info(
                f"Found {len(results)} matches for '{query_company}' with scores: "
                f"{[(name, f'{score:.1f}') for name, score in results[:3]]}"
            )

        return results

    except Exception as e:
        logger.exception(f"Error during fuzzy matching: {e}")
        return []


def get_best_match(
    query_company: str,
    all_companies: Set[str],
    threshold: int = DEFAULT_THRESHOLD,
) -> str | None:
    """
    Get the single best matching company name.

    Args:
        query_company: The company name from the user query
        all_companies: Set of all available company names
        threshold: Minimum similarity score (0-100). Default 75.

    Returns:
        The best matching company name, or None if no match above threshold

    Examples:
        >>> companies = {"ABC Corporation", "XYZ Ltd"}
        >>> get_best_match("ABC Corp", companies)
        "ABC Corporation"
    """
    matches = find_similar_company_names(
        query_company=query_company,
        all_companies=all_companies,
        threshold=threshold,
        max_matches=1,
    )

    return matches[0] if matches else None


def normalize_company_name(company_name: str) -> str:
    """
    Normalize a company name for better matching.

    Applies common normalizations:
    - Strips whitespace
    - Converts to lowercase for comparison
    - Removes common suffixes (株式会社, Ltd, Inc, Corp, etc.)

    Args:
        company_name: The company name to normalize

    Returns:
        Normalized company name
    """
    if not company_name:
        return ""

    # Strip whitespace
    normalized = company_name.strip()

    # Common Japanese company suffixes
    japanese_suffixes = [
        "株式会社",
        "有限会社",
        "合同会社",
        "合資会社",
        "合名会社",
    ]

    # Common English company suffixes
    english_suffixes = [
        " Inc.",
        " Inc",
        " Ltd.",
        " Ltd",
        " Corp.",
        " Corp",
        " LLC",
        " L.L.C.",
        " Co.",
        " Co",
        " Company",
        " AG",  # German: Aktiengesellschaft
        " GmbH",  # German: Gesellschaft mit beschränkter Haftung
        " SA",  # French/Spanish: Société Anonyme / Sociedad Anónima
        " SAS",  # French: Société par Actions Simplifiée
        " NV",  # Dutch: Naamloze Vennootschap
        " BV",  # Dutch: Besloten Vennootschap
        " SpA",  # Italian: Società per Azioni
        " AB",  # Swedish: Aktiebolag
        " AS",  # Norwegian/Danish: Aksjeselskap
        " Oy",  # Finnish: Osakeyhtiö
        " Plc",  # UK: Public Limited Company
        " PLC",
    ]

    # Remove Japanese suffixes (at start or end)
    for suffix in japanese_suffixes:
        if normalized.startswith(suffix):
            normalized = normalized[len(suffix) :].strip()
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()

    # Remove English suffixes (case-insensitive, at end only)
    normalized_lower = normalized.lower()
    for suffix in english_suffixes:
        if normalized_lower.endswith(suffix.lower()):
            normalized = normalized[: -len(suffix)].strip()
            break

    return normalized
