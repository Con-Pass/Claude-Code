from datetime import datetime

from llama_index.core.agent.workflow import FunctionAgent

from app.services.chatbot.prompts.system_prompts_en_v6 import (
    METADATA_CONTROL_PLANE_SYSTEM_PROMPT
)
from app.services.chatbot.tools.metadata_crud.metadata_crud_tools import get_metadata_crud_tools
from app.services.conpass_api_service import ConpassApiService
from llama_index.core.settings import Settings as LLamaIndexSettings


def get_metadata_control_plane_agent(conpass_api_service: ConpassApiService) -> FunctionAgent:
    today = datetime.now().strftime("%Y-%m-%d")
    metadata_crud_tools = get_metadata_crud_tools(
        conpass_api_service=conpass_api_service
    )

    management_system_prompt: str = f"""
            Today's date is {today}.
            {METADATA_CONTROL_PLANE_SYSTEM_PROMPT}
            
        """

    metadata_control_plane_agent = FunctionAgent(
        name="metadata_control_plane_agent",
        description="An agent that performs CRUD operations on metadata for contracts",
        tools=metadata_crud_tools,
        llm=LLamaIndexSettings.llm,
        system_prompt=management_system_prompt,
        verbose=True,
        allow_parallel_tool_calls = False
    )
    return metadata_control_plane_agent