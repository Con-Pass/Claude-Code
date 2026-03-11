from typing import List, Optional

from llama_index.core.agent.workflow import FunctionAgent
from llama_index.core.tools import FunctionTool

from app.core.logging_config import get_logger
from llama_index.core.settings import Settings as LLamaIndexSettings
from app.services.chatbot.prompts.system_prompts_en_v6 import (
    ORCHESTRATOR_SYSTEM_PROMPT,
)
from app.services.chatbot.tools.compliance.compliance_tool import (
    get_compliance_summary_tool,
    get_contract_compliance_tool,
)

logger = get_logger(__name__)


def get_orchestrator_tools() -> List[FunctionTool]:
    """
    オーケストレーターが直接実行できるツールリストを返す。

    これらはサブエージェントへのルーティングを必要とせず、
    オーケストレーター自身が直接回答できる軽量な照会ツール。
    """
    return [
        get_compliance_summary_tool(),
        get_contract_compliance_tool(),
    ]


def get_orchestrator_agent() -> FunctionAgent:
    orchestrator_agent = FunctionAgent(
        name="orchestrator_agent",
        description="An orchestrator agent that routes requests to specialized agents based on user intent",
        tools=get_orchestrator_tools(),
        llm=LLamaIndexSettings.llm,
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        verbose=True,
        allow_parallel_tool_calls=True,
    )
    return orchestrator_agent
