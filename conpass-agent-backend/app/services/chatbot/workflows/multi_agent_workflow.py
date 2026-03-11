from typing import List
from llama_index.core.base.llms.types import MessageRole
from app.schemas.chat import SessionType
from app.services.chatbot.agents.contract_and_document_intelligence_agent import (
    get_contract_and_document_intelligence_agent,
)
from app.services.chatbot.agents.metadata_control_plane_agent import (
    get_metadata_control_plane_agent,
)
from app.services.chatbot.agents.orchestrator_agent import get_orchestrator_agent
from app.services.conpass_api_service import ConpassApiService
from llama_index.core.agent.workflow import AgentWorkflow


class MultiAgentWorkflow:
    def __init__(
        self,
        directory_ids: List[int],
        conpass_api_service: ConpassApiService,
        session_type: SessionType = SessionType.GENERAL,
        event_handlers=None,
        role: MessageRole = MessageRole.USER,
    ):
        self.directory_ids = directory_ids
        self.conpass_api_service = conpass_api_service
        self.session_type = session_type
        self.event_handlers = event_handlers or []
        self.workflow = None
        self.role = role

    def get_multi_agent_workflow(self) -> AgentWorkflow:
        orchestrator_agent = get_orchestrator_agent()
        metadata_control_plane_agent = get_metadata_control_plane_agent(
            conpass_api_service=self.conpass_api_service,
        )
        contract_and_document_intelligence_agent = (
            get_contract_and_document_intelligence_agent(
                conpass_api_service=self.conpass_api_service,
                directory_ids=self.directory_ids,
                session_type=self.session_type,
            )
        )
        metadata_control_plane_agent.can_handoff_to = [orchestrator_agent.name]
        contract_and_document_intelligence_agent.can_handoff_to = [
            orchestrator_agent.name
        ]
        orchestrator_agent.can_handoff_to = [
            metadata_control_plane_agent.name,
            contract_and_document_intelligence_agent.name,
        ]
        root_agent: str = orchestrator_agent.name
        if self.role == MessageRole.SYSTEM:
            root_agent = metadata_control_plane_agent.name

        multi_agent_workflow = AgentWorkflow(
            agents=[
                orchestrator_agent,
                metadata_control_plane_agent,
                contract_and_document_intelligence_agent,
            ],
            verbose=True,
            root_agent=root_agent,
        )
        return multi_agent_workflow
