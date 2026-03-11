# """Utilities for converting filter responses to Qdrant-compatible dictionaries."""

# from typing import Optional, Dict, Any

# from app.schemas.qdrant_filter import QdrantFilterResponse


# def convert_filter_to_dict(
#     filter_response: QdrantFilterResponse,
# ) -> Optional[Dict[str, Any]]:
#     """
#     Convert the Pydantic filter model to a dictionary suitable for Qdrant API.

#     Args:
#         filter_response: The QdrantFilterResponse from LLM

#     Returns:
#         Dictionary representation of the filter, or None if no filter
#     """
#     if not filter_response.filter:
#         return None

#     def process_condition(condition):
#         """Recursively process conditions to convert to dict."""
#         if isinstance(condition, dict):
#             return condition
#         return condition.model_dump(exclude_none=True, by_alias=True)

#     filter_dict = {}

#     if filter_response.filter.must:
#         filter_dict["must"] = [
#             process_condition(c) for c in filter_response.filter.must
#         ]

#     if filter_response.filter.should:
#         filter_dict["should"] = [
#             process_condition(c) for c in filter_response.filter.should
#         ]

#     if filter_response.filter.must_not:
#         filter_dict["must_not"] = [
#             process_condition(c) for c in filter_response.filter.must_not
#         ]

#     return filter_dict if filter_dict else None
