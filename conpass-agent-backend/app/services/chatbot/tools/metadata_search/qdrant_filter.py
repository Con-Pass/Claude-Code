from __future__ import annotations

from typing import Optional, List, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict


METADATA_KEY_MAP = {
    "title": "契約書名_title",
    "contract_title": "契約書名_title",
    "company_a": "会社名_甲_company_a",
    "companya": "会社名_甲_company_a",
    "party_a": "会社名_甲_company_a",
    "party_b": "会社名_乙_company_b",
    "party_c": "会社名_丙_company_c",
    "party_d": "会社名_丁_company_d",
    "company_b": "会社名_乙_company_b",
    "companyb": "会社名_乙_company_b",
    "company_c": "会社名_丙_company_c",
    "companyc": "会社名_丙_company_c",
    "company_d": "会社名_丁_company_d",
    "companyd": "会社名_丁_company_d",
    "contract_date": "契約日_contract_date",
    "contractstartdate": "契約開始日_contract_start_date",
    "contract_start_date": "契約開始日_contract_start_date",
    "contractenddate": "契約終了日_contract_end_date",
    "contract_end_date": "契約終了日_contract_end_date",
    "cancel_notice_date": "契約終了日_cancel_notice_date",
    "auto_update": "自動更新の有無_auto_update",
    "autoupdate": "自動更新の有無_auto_update",
    "court": "裁判所_court",
    "contract_type": "契約種別_contract_type",
    "contracttype": "契約種別_contract_type",
    "contract_id": "contract_id",
    "contractid": "contract_id",
}


def resolve_metadata_key(key: Optional[str]) -> Optional[str]:
    if key is None:
        return None
    if key in METADATA_KEY_MAP.values():
        return key
    normalized = key.strip().lower().replace(" ", "_")
    return METADATA_KEY_MAP.get(normalized, key)


class QdrantBaseModel(BaseModel):
    """Base model for Qdrant filter schemas."""

    model_config = ConfigDict(extra="ignore")


# Match conditions
class MatchValue(QdrantBaseModel):
    """Match a specific value"""

    value: Union[str, int, bool] = Field(description="The value to match")


class MatchAny(QdrantBaseModel):
    """Match any of the provided values (OR operation)"""

    any: List[Union[str, int]] = Field(description="List of values to match (any)")


class MatchExcept(QdrantBaseModel):
    """Match values not in the list (NOT IN operation)"""

    except_: List[Union[str, int]] = Field(
        alias="except", description="List of values to exclude"
    )


# MatchText and MatchPhrase removed - they require text indexes which are not configured.
# Use MatchValue for exact string matching instead.


# Range conditions
class RangeCondition(QdrantBaseModel):
    """Range condition for numeric or date values. Only include the operators you need - omit unused ones."""

    gt: Optional[Union[float, int, str]] = Field(
        default=None, description="Greater than. Omit this field if not used."
    )
    gte: Optional[Union[float, int, str]] = Field(
        default=None, description="Greater than or equal. Omit this field if not used."
    )
    lt: Optional[Union[float, int, str]] = Field(
        default=None, description="Less than. Omit this field if not used."
    )
    lte: Optional[Union[float, int, str]] = Field(
        default=None, description="Less than or equal. Omit this field if not used."
    )

    def model_dump(self, **kwargs):
        """Override to exclude None values by default"""
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(**kwargs)

    def model_dump_json(self, **kwargs):
        """Override to exclude None values by default"""
        kwargs.setdefault("exclude_none", True)
        return super().model_dump_json(**kwargs)


# Base condition types
class FieldCondition(QdrantBaseModel):
    """A condition on a specific field. Use EITHER match OR range, never both. Omit the field you don't use."""

    key: str = Field(description="The metadata field name to filter on")
    match: Optional[Union[MatchValue, MatchAny, MatchExcept]] = Field(
        default=None,
        description="Match condition for exact values. Use this OR range, not both. Omit if using range.",
    )
    range: Optional[RangeCondition] = Field(
        default=None,
        description="Range condition for numeric/date comparisons. Use this OR match, not both. Omit if using match.",
    )

    @field_validator("key", mode="before")
    @classmethod
    def _normalize_key(cls, value):
        return resolve_metadata_key(value)

    def model_dump(self, **kwargs):
        """Override to exclude None values by default"""
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(**kwargs)

    def model_dump_json(self, **kwargs):
        """Override to exclude None values by default"""
        kwargs.setdefault("exclude_none", True)
        return super().model_dump_json(**kwargs)


class FieldReference(QdrantBaseModel):
    """Reference to a metadata field key"""

    key: str = Field(description="The metadata field name to reference")

    @field_validator("key", mode="before")
    @classmethod
    def _normalize_key(cls, value):
        return resolve_metadata_key(value)


class IsEmptyCondition(QdrantBaseModel):
    """Check if field is empty"""

    is_empty: FieldReference = Field(description="Field to check if empty")


class IsNullCondition(QdrantBaseModel):
    """Check if field is null"""

    is_null: FieldReference = Field(description="Field to check if null")


class HasIdCondition(QdrantBaseModel):
    """Filter by point IDs"""

    has_id: List[Union[str, int]] = Field(description="List of point IDs to filter")


# Flat conditions (no nesting)
FlatConditionType = Union[
    FieldCondition,
    HasIdCondition,
    IsEmptyCondition,
    IsNullCondition,
]


# Nested filter - supports ONE level of nesting only
class NestedFilter(QdrantBaseModel):
    """
    Nested filter clause - ONE LEVEL DEEP ONLY.
    Use this to create complex AND/OR/NOT logic within a parent filter.
    This cannot contain other NestedFilter objects.
    """

    must: Optional[List[FlatConditionType]] = Field(
        default=None,
        description="All conditions must be satisfied (AND). Omit this field if not used.",
    )
    should: Optional[List[FlatConditionType]] = Field(
        default=None,
        description="At least one condition must be satisfied (OR). Omit this field if not used.",
    )
    must_not: Optional[List[FlatConditionType]] = Field(
        default=None,
        description="None of the conditions should be satisfied (NOT). Omit this field if not used.",
    )

    def model_dump(self, **kwargs):
        """Override to exclude None values by default"""
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(**kwargs)

    def model_dump_json(self, **kwargs):
        """Override to exclude None values by default"""
        kwargs.setdefault("exclude_none", True)
        return super().model_dump_json(**kwargs)


# Top-level condition type (can include nested filters)
ConditionType = Union[
    FieldCondition,
    NestedFilter,
    HasIdCondition,
    IsEmptyCondition,
    IsNullCondition,
]


# Top-level filter
class Filter(QdrantBaseModel):
    """
    Top-level Qdrant filter with must, should, must_not clauses.
    Only include the clauses you need - omit unused ones.
    Can contain FieldCondition or NestedFilter for one level of nesting.
    """

    must: Optional[List[ConditionType]] = Field(
        default=None,
        description="All conditions must be satisfied (AND). Omit this field if not used.",
    )
    should: Optional[List[ConditionType]] = Field(
        default=None,
        description="At least one condition must be satisfied (OR). Omit this field if not used.",
    )
    must_not: Optional[List[ConditionType]] = Field(
        default=None,
        description="None of the conditions should be satisfied (NOT). Omit this field if not used.",
    )

    def model_dump(self, **kwargs):
        """Override to exclude None values by default"""
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(**kwargs)

    def model_dump_json(self, **kwargs):
        """Override to exclude None values by default"""
        kwargs.setdefault("exclude_none", True)
        return super().model_dump_json(**kwargs)


class QdrantFilterResponse(QdrantBaseModel):
    """Response schema for converting natural language to Qdrant filters"""

    filter: Optional[Filter] = Field(
        default=None,
        description="The Qdrant filter object with must/should/must_not clauses",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Brief explanation of how the query was interpreted. Include the English part of the key names in your explanation.",
    )


class FilterValidationResponse(QdrantBaseModel):
    """Response schema for validating Qdrant filters"""

    is_correct: bool = Field(
        description="Whether the filter is correct (structurally valid and logically sound)"
    )
    feedback: Optional[str] = Field(
        default=None,
        description="Explanation of why the filter is incorrect, or confirmation if correct. If incorrect, provide specific guidance on what needs to be fixed.",
    )
