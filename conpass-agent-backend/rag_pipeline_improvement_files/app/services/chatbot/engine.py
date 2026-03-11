from datetime import datetime
from typing import List, Optional
from llama_index.core.base.llms.types import MessageRole
from app.core.logging_config import get_logger
from app.services.chatbot.agent_adapter import WorkflowAgentChatAdapter
from app.schemas.chat import SessionType
from app.services.chatbot.prompts.system_prompts_jp_v3 import (
    CONPASS_ONLY_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
)
from app.services.chatbot.tools.tools import get_all_tools
from app.services.chatbot.workflows.multi_agent_workflow import MultiAgentWorkflow
from app.services.chatbot.feature_flags import should_use_multi_agent
from app.services.conpass_api_service import ConpassApiService
from llama_index.core.agent.workflow import AgentWorkflow
from llama_index.core.settings import Settings as LLamaIndexSettings

logger = get_logger(__name__)


def get_chat_engine(
    directory_ids: List[int],
    conpass_api_service: ConpassApiService,
    session_type: SessionType = SessionType.GENERAL,
    event_handlers=None,
    role: MessageRole = MessageRole.USER,
    session_id: Optional[str] = None,
) -> WorkflowAgentChatAdapter:
    # 機能フラグベースのマルチエージェント判定
    use_multi_agent = should_use_multi_agent(session_id)

    if use_multi_agent:
        logger.info(f"Using multi-agent workflow (session_id={session_id})")
        multi_agent_workflow = MultiAgentWorkflow(
            directory_ids=directory_ids,
            conpass_api_service=conpass_api_service,
            session_type=session_type,
            role=role,
        ).get_multi_agent_workflow()

        return WorkflowAgentChatAdapter(
            multi_agent_workflow, event_handlers=event_handlers
        )

    else:
        system_prompt = None

        if session_type == SessionType.CONPASS_ONLY:
            system_prompt = CONPASS_ONLY_SYSTEM_PROMPT
        else:
            system_prompt = SYSTEM_PROMPT

        today = datetime.now().strftime("%Y-%m-%d")

        system_prompt = f"""
            Today's date is {today}.

            {system_prompt}
        """

        tools = get_all_tools(
            session_type=session_type,
            directory_ids=directory_ids,
            conpass_api_service=conpass_api_service,
        )

        agent_workflow = AgentWorkflow.from_tools_or_functions(
            tools_or_functions=tools,
            llm=LLamaIndexSettings.llm,
            system_prompt=system_prompt,
            verbose=True,
        )

        return WorkflowAgentChatAdapter(agent_workflow, event_handlers=event_handlers)
