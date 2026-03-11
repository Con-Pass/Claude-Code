# """Tool factory for creating the text-to-qdrant-filter FunctionTool."""

# from datetime import datetime
# from llama_index.core.tools import FunctionTool

# from app.services.chatbot.tools.qdrant_filter_tool.query_executor import (
#     query_contracts_by_metadata,
# )


# def get_text_to_qdrant_filter_tool() -> FunctionTool:
#     """
#     Get the text-to-qdrant-filter tool as a LlamaIndex FunctionTool.

#     Returns:
#         FunctionTool that can be used by the agent
#     """
#     today = datetime.now().strftime("%Y-%m-%d")

#     return FunctionTool.from_defaults(
#         async_fn=query_contracts_by_metadata,
#         name="query_contracts",
#         description=f"""
#         Today's date is {today}.

#         Use this tool to query and retrieve contract documents based on metadata filters.
#         This tool converts natural language queries into Qdrant filters and retrieves matching contracts.

#         This tool can handle complex queries involving:
#         - Company names (company_a, company_b, company_c, company_d)
#         - Contract dates (contract_date, contract_start_date, contract_end_date, cancel_notice_date)
#         - Contract types (contract_type)
#         - Auto-renewal status (auto_update) - boolean true/false
#         - Court jurisdiction (court)
#         - Contract title (title)

#         Supports complex filtering logic:
#         - AND conditions: "Show contracts with 株式会社ABC that end after 2024-06-01"
#         - OR conditions: "Find contracts with 株式会社ABC or 株式会社XYZ"
#         - NOT conditions: "Show contracts ending in 2024 but not with 株式会社ABC"
#         - Date ranges: "Find contracts ending between 2024-01-01 and 2024-12-31"
#         - Boolean filters: "Show contracts with auto-renewal enabled"

#         Examples:
#         - "Find contracts with 株式会社ABC"
#         - "Show contracts ending in 2024"
#         - "Get auto-renewal contracts with company XYZ"
#         - "Find contracts that end this year but are not with company ABC"
#         - "Show contracts with company A as 株式会社DEF and contract type as 売買契約"

#         Note: This tool retrieves contracts from the vector database based on metadata only.
#         Use contract_fetch_tool if you need to query the ConPass API directly.
#         """,
#     )
