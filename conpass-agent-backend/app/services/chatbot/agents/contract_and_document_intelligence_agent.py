from datetime import datetime
from typing import List

from llama_index.core.agent.workflow import FunctionAgent

from app.schemas.chat import SessionType
from app.services.chatbot.tools.tools import get_assistant_tools
from app.services.conpass_api_service import ConpassApiService
from llama_index.core.settings import Settings as LLamaIndexSettings

# from app.services.chatbot.prompts.system_prompts_en_v6 import (
#     CONPASS_ONLY_CONTRACT_AND_DOCUMENT_INTELLIGENCE_SYSTEM_PROMPT,
#     GENERAL_CONTRACT_AND_DOCUMENT_INTELLIGENCE_SYSTEM_PROMPT,
# )
from app.services.chatbot.prompts.system_prompts_jp_v5 import (
    SYSTEM_PROMPT,
    CONPASS_ONLY_SYSTEM_PROMPT,
)


def get_contract_and_document_intelligence_agent(
    session_type: SessionType,
    directory_ids: List[int],
    conpass_api_service: ConpassApiService,
) -> FunctionAgent:
    today = datetime.now().strftime("%Y-%m-%d")
    if session_type == SessionType.CONPASS_ONLY:
        # system_prompt = CONPASS_ONLY_CONTRACT_AND_DOCUMENT_INTELLIGENCE_SYSTEM_PROMPT
        system_prompt = CONPASS_ONLY_SYSTEM_PROMPT
    else:
        # system_prompt = GENERAL_CONTRACT_AND_DOCUMENT_INTELLIGENCE_SYSTEM_PROMPT
        system_prompt = SYSTEM_PROMPT

    system_prompt = f"""
        Today's date is {today}.

        {system_prompt}        
    """

    tools = get_assistant_tools(
        session_type=session_type,
        directory_ids=directory_ids,
        conpass_api_service=conpass_api_service,
    )

    contract_and_document_intelligence_agent = FunctionAgent(
        name="contract_and_document_intelligence_agent",
        description="An agent that answers questions about contracts and documents",
        tools=tools,
        llm=LLamaIndexSettings.llm,
        system_prompt=system_prompt,
        verbose=True,
        allow_parallel_tool_calls=False,
    )
    return contract_and_document_intelligence_agent
