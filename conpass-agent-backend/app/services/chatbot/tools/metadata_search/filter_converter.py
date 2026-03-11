import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from app.services.chatbot.tools.metadata_search.qdrant_filter import (
    QdrantFilterResponse,
    FieldCondition,
)
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Qdrant ペイロードで epoch 変換が必要な日付フィールド
# (Qdrant RangeCondition は数値のみ有効。文字列比較は動作しない)
_DATE_EPOCH_FIELDS = {
    "契約日_contract_date",
    "契約開始日_contract_start_date",
    "契約終了日_contract_end_date",
}


def _iso_to_epoch(value: Any) -> Optional[float]:
    """YYYY-MM-DD 文字列または数値を epoch float に変換。失敗時は None。"""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            return None
    return None


def sanitize_range_value(value: Any) -> Optional[Any]:
    """
    Sanitize and validate range values (dates, numbers).

    Removes invalid characters and validates date format (YYYY-MM-DD).
    Returns None if value cannot be sanitized.
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return value

    if isinstance(value, bool):
        return None  # Booleans are not valid range values

    if not isinstance(value, str):
        return None

    # Remove any invalid characters that might have been introduced by malformed JSON
    # This handles cases like "2020-12-31}}]},"
    cleaned = value.strip()

    # Remove trailing invalid characters (closing braces, brackets, commas, etc.)
    cleaned = re.sub(r"[}\]],]*$", "", cleaned)

    # Check if it looks like a date (YYYY-MM-DD format)
    date_pattern = r"^\d{4}-\d{2}-\d{2}$"
    if re.match(date_pattern, cleaned):
        return cleaned

    # Try to parse as number
    try:
        # Check if it's a float
        if "." in cleaned:
            return float(cleaned)
        return int(cleaned)
    except ValueError:
        # If it's not a valid number or date, return None
        logger.warning(f"Invalid range value after sanitization: {value} -> {cleaned}")
        return None


def sanitize_match_value(value: Any) -> Any:
    """
    Sanitize match values (strings, integers, booleans).

    Removes invalid trailing characters that might have been introduced by malformed JSON
    (e.g., trailing }}]}}, from JSON template escaping).
    """
    if value is None:
        return None

    # For non-string types, return as-is (integers, booleans)
    if not isinstance(value, str):
        return value

    # Remove any invalid characters that might have been introduced by malformed JSON
    # This handles cases like "雇用契約書}}]}},"
    cleaned = value.strip()

    # Remove trailing invalid characters (closing braces, brackets, commas, etc.)
    cleaned = re.sub(r"[}\]],]*$", "", cleaned)

    return cleaned


def sanitize_match_condition(match_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize a match condition dictionary.

    Cleans string values in match.value, match.any, and match.except.
    Converts match.text to match.value as a safety net (MatchText is no longer supported).
    """
    if not isinstance(match_dict, dict):
        return match_dict

    sanitized = match_dict.copy()

    # Convert match.text to match.value (safety net for legacy/edge cases)
    # MatchText is no longer supported as it requires a text index.
    # This conversion handles any edge cases where "text" might appear.
    if "text" in sanitized:
        text_value = sanitize_match_value(sanitized["text"])
        # Remove "text" key
        sanitized.pop("text")
        # Only set "value" if it doesn't already exist (shouldn't happen, but safety check)
        if "value" not in sanitized:
            sanitized["value"] = text_value
            logger.debug(f"Converted match.text to match.value: {text_value}")
        else:
            logger.warning(
                f"Both 'text' and 'value' found in match condition, keeping 'value': {sanitized.get('value')}"
            )

    # Sanitize match.value
    if "value" in sanitized:
        sanitized["value"] = sanitize_match_value(sanitized["value"])

    # Sanitize match.any (list of values)
    if "any" in sanitized and isinstance(sanitized["any"], list):
        sanitized["any"] = [sanitize_match_value(v) for v in sanitized["any"]]

    # Sanitize match.except (list of values)
    if "except" in sanitized and isinstance(sanitized["except"], list):
        sanitized["except"] = [sanitize_match_value(v) for v in sanitized["except"]]

    # Sanitize match.phrase (safety net - MatchPhrase is no longer supported)
    if "phrase" in sanitized:
        phrase_value = sanitize_match_value(sanitized["phrase"])
        sanitized.pop("phrase")
        if "value" not in sanitized:
            sanitized["value"] = phrase_value
            logger.debug(f"Converted match.phrase to match.value: {phrase_value}")

    return sanitized


def sanitize_range_condition(range_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Sanitize a range condition dictionary.

    Also removes conflicting/redundant operators:
    - If both 'gt' and 'gte' exist, keeps the more restrictive one (gt)
    - If both 'lt' and 'lte' exist, keeps the more restrictive one (lt)

    Returns a cleaned range dict or None if no valid range values remain.
    """
    if not isinstance(range_dict, dict):
        return None

    sanitized = {}
    has_valid_value = False

    for key in ["gt", "gte", "lt", "lte"]:
        if key in range_dict:
            sanitized_value = sanitize_range_value(range_dict[key])
            if sanitized_value is not None:
                sanitized[key] = sanitized_value
                has_valid_value = True

    # Remove conflicting operators - gt and gte should never be used together
    # Prefer gte over gt (more inclusive) as a safety net if validation didn't catch it
    if "gt" in sanitized and "gte" in sanitized:
        # Remove gt, keep gte (more inclusive)
        removed_value = sanitized.pop("gt")
        logger.warning(
            f"Removed 'gt' ({removed_value}) as 'gte' ({sanitized.get('gte')}) is also present. "
            f"gt and gte should not be used together - keeping gte for more inclusive filtering."
        )

    # Remove conflicting operators - lt and lte should never be used together
    # Prefer lte over lt (more inclusive) as a safety net if validation didn't catch it
    if "lt" in sanitized and "lte" in sanitized:
        # Remove lt, keep lte (more inclusive)
        removed_value = sanitized.pop("lt")
        logger.warning(
            f"Removed 'lt' ({removed_value}) as 'lte' ({sanitized.get('lte')}) is also present. "
            f"lt and lte should not be used together - keeping lte for more inclusive filtering."
        )

    return sanitized if has_valid_value else None


def is_valid_condition_dict(condition_dict: Dict[str, Any]) -> bool:
    """
    Validate that a condition dictionary is properly formed.

    Checks for:
    - Empty objects (no valid fields)
    - Invalid range conditions
    - Missing required fields
    """
    if not isinstance(condition_dict, dict):
        return False

    # Check for empty objects (like {"must": null, "should": null, "must_not": null})
    if not condition_dict:
        return False

    # Check if it's a Filter object (nested filter)
    if any(key in condition_dict for key in ["must", "should", "must_not"]):
        # It's a nested filter - validate it recursively
        has_valid_clause = False
        for clause_key in ["must", "should", "must_not"]:
            if clause_key in condition_dict and condition_dict[clause_key]:
                if (
                    isinstance(condition_dict[clause_key], list)
                    and len(condition_dict[clause_key]) > 0
                ):
                    has_valid_clause = True
                    break
        return has_valid_clause

    # Check if it's a FieldCondition
    if "key" in condition_dict:
        # Must have either match or range
        if "match" in condition_dict and condition_dict["match"] is not None:
            return True
        if "range" in condition_dict and condition_dict["range"] is not None:
            # Validate range (don't modify dict here, sanitization happens in process_condition)
            sanitized_range = sanitize_range_condition(condition_dict["range"])
            return sanitized_range is not None
        return False

    # Check for other condition types (has_id, is_empty, is_null)
    if any(key in condition_dict for key in ["has_id", "is_empty", "is_null"]):
        return True

    # Unknown condition type
    return False


def convert_filter_to_dict(
    filter_response: QdrantFilterResponse,
) -> Optional[Dict[str, Any]]:
    """
    Convert the Pydantic filter model to a dictionary suitable for Qdrant API.

    Args:
        filter_response: The QdrantFilterResponse from LLM

    Returns:
        Dictionary representation of the filter, or None if no filter
    """
    if not filter_response.filter:
        return None

    def is_valid_condition(condition) -> bool:
        """
        Check if a condition is valid (has at least one filter criteria).

        FieldCondition must have at least match or range specified.
        Other condition types are always valid.
        """
        # Handle dict conditions (can happen if structured output parsing partially fails)
        if isinstance(condition, dict):
            return is_valid_condition_dict(condition)

        if isinstance(condition, FieldCondition):
            # FieldCondition must have at least match or range
            if condition.match is not None:
                return True
            if condition.range is not None:
                # Validate range values
                range_dict = condition.range.model_dump(
                    exclude_none=True, by_alias=True
                )
                sanitized = sanitize_range_condition(range_dict)
                return sanitized is not None
            return False
        # Other condition types (Filter, HasIdCondition, IsEmptyCondition, IsNullCondition)
        # are always valid
        return True

    def process_condition(condition):
        """Recursively process conditions to convert to dict."""
        if isinstance(condition, dict):
            # Create a copy to avoid modifying the original
            condition = condition.copy()
            # Sanitize match conditions in dict format
            if "match" in condition and isinstance(condition["match"], dict):
                condition["match"] = sanitize_match_condition(condition["match"])
            # Sanitize range conditions in dict format
            if "range" in condition and isinstance(condition["range"], dict):
                sanitized_range = sanitize_range_condition(condition["range"])
                if sanitized_range:
                    condition["range"] = sanitized_range
                else:
                    # Remove range if invalid
                    condition.pop("range", None)
            return condition

        condition_dict = condition.model_dump(exclude_none=True, by_alias=True)

        # Sanitize match conditions
        if "match" in condition_dict and isinstance(condition_dict["match"], dict):
            condition_dict["match"] = sanitize_match_condition(condition_dict["match"])
        # Sanitize range conditions
        if "range" in condition_dict and isinstance(condition_dict["range"], dict):
            sanitized_range = sanitize_range_condition(condition_dict["range"])
            if sanitized_range:
                condition_dict["range"] = sanitized_range
            else:
                # Remove range if invalid
                condition_dict.pop("range", None)

        # 日付フィールドの range を _epoch フィールドに書き換え
        # Qdrant RangeCondition は float のみ有効。ISO 文字列は無視されるため変換が必要。
        if (
            condition_dict.get("key") in _DATE_EPOCH_FIELDS
            and "range" in condition_dict
        ):
            condition_dict["key"] = condition_dict["key"] + "_epoch"
            orig_range = condition_dict["range"]
            new_range = {}
            for op in ("gt", "gte", "lt", "lte"):
                if op in orig_range:
                    epoch_val = _iso_to_epoch(orig_range[op])
                    if epoch_val is not None:
                        new_range[op] = epoch_val
            if new_range:
                condition_dict["range"] = new_range
                logger.debug(f"Date field rewritten to epoch: {condition_dict['key']} range={new_range}")
            else:
                # 変換に完全失敗した場合は元に戻す
                condition_dict["key"] = condition_dict["key"].removesuffix("_epoch")
                logger.warning(f"Epoch conversion failed for range: {orig_range}")

        return condition_dict

    filter_dict = {}

    if filter_response.filter.must:
        # Filter out invalid conditions (e.g., FieldCondition with no match/range)
        valid_must = [c for c in filter_response.filter.must if is_valid_condition(c)]
        if valid_must:
            processed_must = [process_condition(c) for c in valid_must]
            # Additional validation on processed conditions
            validated_must = [c for c in processed_must if is_valid_condition_dict(c)]
            if validated_must:
                filter_dict["must"] = validated_must
            elif processed_must:
                logger.warning(
                    f"Some 'must' conditions were filtered out after processing: "
                    f"{len(processed_must) - len(validated_must) if validated_must else len(processed_must)} invalid conditions"
                )

    if filter_response.filter.should:
        # Filter out invalid conditions
        valid_should = [
            c for c in filter_response.filter.should if is_valid_condition(c)
        ]
        if valid_should:
            processed_should = [process_condition(c) for c in valid_should]
            # Additional validation on processed conditions
            validated_should = [
                c for c in processed_should if is_valid_condition_dict(c)
            ]
            if validated_should:
                filter_dict["should"] = validated_should
            elif processed_should:
                logger.warning(
                    f"Some 'should' conditions were filtered out after processing: "
                    f"{len(processed_should) - len(validated_should) if validated_should else len(processed_should)} invalid conditions"
                )

    if filter_response.filter.must_not:
        # Filter out invalid conditions
        valid_must_not = [
            c for c in filter_response.filter.must_not if is_valid_condition(c)
        ]
        if valid_must_not:
            processed_must_not = [process_condition(c) for c in valid_must_not]
            # Additional validation on processed conditions
            validated_must_not = [
                c for c in processed_must_not if is_valid_condition_dict(c)
            ]
            if validated_must_not:
                filter_dict["must_not"] = validated_must_not
            elif processed_must_not:
                logger.warning(
                    f"Some 'must_not' conditions were filtered out after processing: "
                    f"{len(processed_must_not) - len(validated_must_not) if validated_must_not else len(processed_must_not)} invalid conditions"
                )

    if filter_dict:
        logger.debug(f"Final filter dict: {filter_dict}")
    return filter_dict if filter_dict else None
