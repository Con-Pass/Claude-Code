from typing import List
from app.core.environment_flags import is_development
from app.schemas.chat import SessionType
from llama_index.core.tools import FunctionTool
from app.services.conpass_api_service import ConpassApiService

from app.services.chatbot.tools.csv_generation.csv_generation_tool import (
    get_csv_generation_tool,
)
from app.services.chatbot.tools.metadata_search.metadata_search_tool import (
    get_metadata_search_tool,
)
from app.services.chatbot.tools.read_contracts.read_contracts_tool import (
    get_read_contracts_tool,
)
from app.services.chatbot.tools.risk_analysis.risk_analysis_tool import (
    get_risk_analysis_tool,
)
from app.services.chatbot.tools.semantic_search.semantic_search_tool import (
    get_semantic_search_tool,
)
from app.services.chatbot.tools.web_search.web_search_tool import get_web_search_tools
from app.services.chatbot.tools.fetch_file_content.fetch_file_content_tool import (
    get_file_content_tool,
)
from app.services.chatbot.tools.document_diffing.document_diffing_tool import (
    get_document_diffing_tool,
)
from app.services.chatbot.tools.metadata_crud.read_directory import (
    get_read_directory_tool,
)
from app.services.chatbot.tools.benchmark_tool import (
    get_benchmark_stats_tool,
    get_benchmark_compare_tool,
)
from app.services.chatbot.tools.template_compare_tool import (
    get_template_list_tool,
    get_template_compare_tool,
)
from app.services.chatbot.tools.law_search.law_search_tool import get_law_search_tool
from app.services.chatbot.tools.metadata_search.aggregate_tool import (
    get_aggregate_contracts_tool,
)


def get_all_tools(
    session_type: SessionType,
    directory_ids: List[int],
    conpass_api_service: ConpassApiService,
) -> list[FunctionTool]:
    tools = []
    if is_development():
        common_tools = [
            get_semantic_search_tool(directory_ids=directory_ids),
            get_metadata_search_tool(directory_ids=directory_ids),
            get_aggregate_contracts_tool(
                directory_ids=directory_ids, conpass_api_service=conpass_api_service
            ),
            get_read_contracts_tool(
                directory_ids=directory_ids, conpass_api_service=conpass_api_service
            ),
            get_file_content_tool(),
            get_csv_generation_tool(directory_ids=directory_ids),
            get_document_diffing_tool(),
            get_law_search_tool(directory_ids=directory_ids),
        ]
    else:
        common_tools = [
            get_semantic_search_tool(directory_ids=directory_ids),
            get_metadata_search_tool(directory_ids=directory_ids),
            get_aggregate_contracts_tool(
                directory_ids=directory_ids, conpass_api_service=conpass_api_service
            ),
            get_read_contracts_tool(
                directory_ids=directory_ids, conpass_api_service=conpass_api_service
            ),
            get_law_search_tool(directory_ids=directory_ids),
        ]

    exclusive_tools = [
        get_web_search_tools(),
        get_risk_analysis_tool(
            directory_ids=directory_ids, conpass_api_service=conpass_api_service
        ),
    ]
    tools = (
        common_tools
        if session_type == SessionType.CONPASS_ONLY
        else common_tools + exclusive_tools
    )

    return tools


def get_assistant_tools(
    session_type: SessionType,
    directory_ids: List[int],
    conpass_api_service: ConpassApiService,
) -> list[FunctionTool]:
    tools = []
    common_tools = [
        get_semantic_search_tool(directory_ids=directory_ids),
        get_metadata_search_tool(directory_ids=directory_ids),
        get_aggregate_contracts_tool(
            directory_ids=directory_ids, conpass_api_service=conpass_api_service
        ),
        get_read_contracts_tool(
            directory_ids=directory_ids, conpass_api_service=conpass_api_service
        ),
        get_read_directory_tool(conpass_api_service=conpass_api_service),
        get_file_content_tool(),
        get_csv_generation_tool(directory_ids=directory_ids),
        get_document_diffing_tool(),
        get_benchmark_stats_tool(),
        get_benchmark_compare_tool(),
        get_template_list_tool(),
        get_template_compare_tool(),
        get_law_search_tool(directory_ids=directory_ids),
    ]

    exclusive_tools = [
        get_web_search_tools(),
        get_risk_analysis_tool(
            directory_ids=directory_ids, conpass_api_service=conpass_api_service
        ),
    ]
    tools = (
        common_tools
        if session_type == SessionType.CONPASS_ONLY
        else common_tools + exclusive_tools
    )

    return tools
