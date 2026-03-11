# from typing import Set
# from datetime import datetime
# import json

# from llama_index.llms.openai import OpenAI

# from app.schemas.qdrant_filter import QdrantFilterResponse
# from app.services.chatbot.tools.tool_prompts import (
#     TEXT_TO_QDRANT_FILTER_PROMPT_TEMPLATE,
# )
# from app.services.chatbot.qdrant_client import scroll_qdrant_with_filter
# from app.core.config import settings
# from app.core.logging_config import get_logger
# from app.services.chatbot.tools.qdrant_filter_tool.docstore import (
#     get_document_from_docstore,
# )
# from app.services.chatbot.tools.qdrant_filter_tool.filter_converter import (
#     convert_filter_to_dict,
# )
# from app.services.chatbot.tools.qdrant_filter_tool.document_utils import (
#     get_document_id,
# )

# logger = get_logger(__name__)


# async def query_contracts_by_metadata(query: str, limit: int = 10) -> str:
#     """
#     Query contracts using natural language by converting to Qdrant filters.

#     This tool converts a natural language query into Qdrant metadata filters
#     and retrieves matching contract documents.

#     Args:
#         query: Natural language query describing what contracts to find.
#                Examples:
#                - "Show me contracts with 株式会社ABC"
#                - "Find contracts ending in 2024"
#                - "Get contracts with auto-renewal that end after 2024-06-01"
#         limit: Maximum number of results to return (default: 10)

#     Returns:
#         A formatted string containing the matching contracts with their metadata and content.
#     """
#     try:
#         logger.info(f"Converting query to Qdrant filter: {query}")

#         # Step 1: Convert natural language to Qdrant filter using LLM
#         today = datetime.now().strftime("%Y-%m-%d")
#         prompt = TEXT_TO_QDRANT_FILTER_PROMPT_TEMPLATE.format(today=today, query=query)

#         llm = OpenAI(
#             model="gpt-5-mini",
#             temperature=0.1,
#             api_key=settings.OPENAI_API_KEY,
#         )

#         sllm = llm.as_structured_llm(QdrantFilterResponse)
#         response = await sllm.acomplete(prompt)
#         filter_response: QdrantFilterResponse = response.raw

#         logger.info(f"Generated filter: {filter_response.model_dump_json(indent=2)}")
#         logger.info(f"Reasoning: {filter_response.reasoning}")

#         # Step 2: Convert to dict format for Qdrant API
#         qdrant_filter = convert_filter_to_dict(filter_response)

#         logger.info(f"Qdrant filter: {qdrant_filter}")

#         # Step 3: Execute the query on Qdrant using scroll (metadata-only)
#         collection_name = settings.QDRANT_COLLECTION
#         if not collection_name:
#             return "Error: QDRANT_COLLECTION not configured"

#         # Step 3a: Execute the initial query on Qdrant using scroll (metadata-only)
#         # We get some matching chunks first to identify which documents match
#         initial_results = await scroll_qdrant_with_filter(
#             collection_name=collection_name,
#             qdrant_filter=qdrant_filter,
#             limit=limit * 10,  # Get more chunks initially to find unique documents
#         )

#         logger.info(f"Initial results: {len(initial_results)} chunks")

#         # Step 4: Extract unique document IDs from initial results
#         if not initial_results:
#             return f"No contracts found matching the query: {query}\n\nFilter used: {json.dumps(qdrant_filter, ensure_ascii=False, indent=2)}"

#         # Get unique document IDs
#         unique_doc_ids: Set[str] = set()
#         for result in initial_results:
#             payload = result.get("payload", {})
#             doc_id = get_document_id(payload)
#             if doc_id:
#                 unique_doc_ids.add(doc_id)

#         # Limit to requested number of unique documents
#         unique_doc_ids_list = list(unique_doc_ids)[:limit]

#         logger.info(
#             f"Found {len(unique_doc_ids_list)} unique document(s): {unique_doc_ids_list}"
#         )

#         # Step 5: Get full documents from docstore
#         documents = {}

#         for doc_id in unique_doc_ids_list:
#             doc_data = await get_document_from_docstore(doc_id)
#             if doc_data:
#                 documents[doc_id] = doc_data
#             else:
#                 logger.warning(f"Document {doc_id} not found in docstore")

#         if not documents:
#             return f"No documents found in docstore for the query: {query}\n\nFound {len(unique_doc_ids_list)} document ID(s) but none were available in docstore."

#         # Step 6: Format the results
#         formatted_results = [
#             f"Query: {query}",
#             f"Filter reasoning: {filter_response.reasoning}",
#             f"Found {len(documents)} unique contract(s)\n",
#             "=" * 80,
#         ]

#         metadata_fields = [
#             ("Title", "契約書名_title"),
#             ("Company A", "会社名_甲_company_a"),
#             ("Company B", "会社名_乙_company_b"),
#             ("Company C", "会社名_丙_company_c"),
#             ("Company D", "会社名_丁_company_d"),
#             ("Contract Type", "契約種別_contract_type"),
#             ("Contract Date", "契約日_contract_date"),
#             ("Start Date", "契約開始日_contract_start_date"),
#             ("End Date", "契約終了日_contract_end_date"),
#             ("Auto Update", "自動更新の有無_auto_update"),
#             ("Cancel Notice Date", "契約終了日_cancel_notice_date"),
#             ("Court", "裁判所_court"),
#         ]

#         for idx, (doc_id, doc_data) in enumerate(documents.items(), 1):
#             metadata = doc_data["metadata"]
#             full_text = doc_data["full_text"]

#             formatted_results.append(f"\n[Contract {idx}]")
#             formatted_results.append(f"Document ID: {doc_id}")

#             # Extract and display metadata
#             formatted_results.append("\nMetadata:")
#             for label, key in metadata_fields:
#                 value = metadata.get(key)
#                 if value is not None:
#                     formatted_results.append(f"  {label}: {value}")

#             # Display full contract text (or excerpt if very long)
#             if full_text:
#                 # Show excerpt if text is very long (>5000 chars), otherwise show full text
#                 if len(full_text) > 5000:
#                     excerpt = (
#                         full_text[:5000]
#                         + f"\n\n... (truncated, total length: {len(full_text)} characters)"
#                     )
#                     formatted_results.append(
#                         f"\nContract Content (excerpt):\n{excerpt}"
#                     )
#                 else:
#                     formatted_results.append(f"\nContract Content:\n{full_text}")

#             formatted_results.append("\n" + "-" * 80)

#         return "\n".join(formatted_results)

#     except Exception as e:
#         logger.exception(f"Error querying contracts by metadata: {e}")
#         return f"Error processing query: {str(e)}"
