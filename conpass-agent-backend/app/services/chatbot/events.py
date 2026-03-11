import asyncio
import json
from app.core.environment_flags import is_development
from app.core.logging_config import get_logger
from typing import Any, AsyncGenerator, Dict, List, Optional

from llama_index.core.callbacks.base import BaseCallbackHandler
from llama_index.core.callbacks.schema import CBEventType
from llama_index.core.tools.types import ToolOutput
from pydantic import BaseModel

logger = get_logger(__name__)


class CallbackEvent(BaseModel):
    event_type: CBEventType
    payload: Optional[Dict[str, Any]] = None
    event_id: str = ""

    def _get_user_friendly_tool_message(
        self, tool_name: str, func_call_args: dict
    ) -> str:
        """Convert technical tool names and inputs to user-friendly messages."""
        tool_messages = {
            "metadata_search": "🔍 契約を検索しています...",
            "semantic_search": "📚 契約内容を検索しています...",
            "risk_analysis_tool": "⚠️ 選択した契約のリスク要因を分析しています...",
            "read_contracts_tool": "📄 契約の詳細を読み込んでいます...",
            "web_search_tool": "🌐 ウェブを検索しています...",
        }

        # Get the user-friendly message or create a default one
        base_message = tool_messages.get(tool_name, "🔧 処理中です...")

        # Add context-specific details for certain tools
        if tool_name == "metadata_search_tool" and func_call_args:
            base_message = "🔍 契約を検索しています..."

        elif tool_name == "semantic_search_tool" and func_call_args:
            query = func_call_args.get("query", "")
            if query:
                base_message = "📚 契約内容を検索しています..."

        elif tool_name == "risk_analysis_tool" and func_call_args:
            contract_ids = func_call_args.get("contract_ids", [])
            if contract_ids:
                ids_str = ", ".join(map(str, contract_ids))
                base_message = f"⚠️ 契約 {ids_str} のリスク要因を分析しています..."

        elif tool_name == "read_contracts_tool" and func_call_args:
            contract_ids = func_call_args.get("contract_ids", [])
            if contract_ids:
                ids_str = ", ".join(map(str, contract_ids))
                base_message = f"📄 契約 {ids_str} の詳細を読み込んでいます..."

        elif tool_name == "web_search_tool" and func_call_args:
            user_query = func_call_args.get("user_query", "")
            base_message = "🌐 ウェブを検索しています..."
            if user_query != "":
                base_message = (
                    f"🌐 ウェブを検索しています... ユーザーのクエリ: {user_query}"
                )

        return base_message

    def get_retrieval_message(self) -> dict | None:
        if self.payload:
            nodes = self.payload.get("nodes")
            if nodes:
                msg = f"✅ Found {len(nodes)} relevant sources for your question"
            else:
                msg = "🔎 Looking for relevant information..."
            return {
                "type": "events",
                "data": {"title": msg},
            }
        else:
            return None

    def get_tool_message(self) -> dict | None:
        if self.payload is None:
            return None
        func_call_args = self.payload.get("function_call")
        if func_call_args is not None and "tool" in self.payload:
            tool = self.payload.get("tool")
            if tool is None:
                return None

            # Get user-friendly message instead of technical details
            user_friendly_msg = self._get_user_friendly_tool_message(
                tool.name, func_call_args
            )

            return {
                "type": "events",
                "data": {
                    "title": user_friendly_msg,
                },
            }
        return None

    def _is_output_serializable(self, output: Any) -> bool:
        try:
            json.dumps(output)
            return True
        except TypeError:
            return False

    def _serialize_output(self, output: Any) -> Any:
        """
        Convert output to a JSON-serializable format.
        Handles Pydantic models by converting them to dicts.
        """
        # If it's a Pydantic BaseModel, convert to dict
        if isinstance(output, BaseModel):
            return output.model_dump()

        # If it's a list, recursively serialize items
        if isinstance(output, list):
            return [self._serialize_output(item) for item in output]

        # If it's a dict, recursively serialize values
        if isinstance(output, dict):
            return {key: self._serialize_output(value) for key, value in output.items()}

        # For other types, check if it's JSON serializable
        if self._is_output_serializable(output):
            return output

        # Fallback to string representation
        return str(output)

    def get_agent_tool_response(self) -> dict | None:
        if self.payload is None:
            return None
        response = self.payload.get("response")
        if response is not None:
            sources = response.sources
            for source in sources:
                # Return the tool response here to include the toolCall information
                if isinstance(source, ToolOutput):
                    if is_development():
                        # Serialize the output properly (handles Pydantic models)
                        if source.raw_output is not None:
                            output = self._serialize_output(source.raw_output)
                        else:
                            output = source.content

                        return {
                            "type": "tools",
                            "data": {
                                "toolOutput": {
                                    "output": output,
                                    "isError": source.is_error,
                                },
                                "toolCall": {
                                    "id": self.event_id if self.event_id else None,
                                    "name": source.tool_name,
                                    "input": source.raw_input,
                                },
                            },
                        }
                    else:
                        if self._is_output_serializable(source.raw_output):
                            output = source.raw_output
                        else:
                            output = source.content

                        return {
                            "type": "tools",
                            "data": {
                                "toolOutput": {
                                    "output": output,
                                    "isError": source.is_error,
                                },
                                "toolCall": {
                                    "id": None,  # There is no tool id in the ToolOutput
                                    "name": source.tool_name,
                                    "input": source.raw_input,
                                },
                            },
                        }
        return None

    def to_response(self):
        try:
            match self.event_type:
                case "retrieve":
                    return self.get_retrieval_message()
                case "function_call":
                    return self.get_tool_message()
                case "agent_step":
                    return self.get_agent_tool_response()
                case _:
                    return None
        except Exception as e:
            logger.error(f"Error in converting event to response: {e}")
            return None


class EventCallbackHandler(BaseCallbackHandler):
    _aqueue: asyncio.Queue
    is_done: bool = False

    def __init__(
        self,
    ):
        """Initialize the base callback handler."""
        ignored_events = [
            CBEventType.CHUNKING,
            CBEventType.NODE_PARSING,
            CBEventType.EMBEDDING,
            CBEventType.LLM,
            CBEventType.TEMPLATING,
        ]
        super().__init__(ignored_events, ignored_events)
        self._aqueue = asyncio.Queue()
        self.captured_tool_outputs = []

    def on_event_start(
        self,
        event_type: CBEventType,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: Any,
    ) -> str:
        event = CallbackEvent(event_id=event_id, event_type=event_type, payload=payload)
        if event.to_response() is not None:
            self._aqueue.put_nowait(event)
        return event_id

    def on_event_end(
        self,
        event_type: CBEventType,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        **kwargs: Any,
    ) -> None:
        event = CallbackEvent(event_id=event_id, event_type=event_type, payload=payload)
        response = event.to_response()
        if response is not None:
            self._aqueue.put_nowait(event)

            # Capture tool outputs for persistence
            if response.get("type") == "tools":
                data = response.get("data", {})
                tool_name = data.get("toolCall", {}).get("name")
                tool_output = data.get("toolOutput", {})
                if tool_name == "csv_generation_tool":
                    logger.info("Captured tool output: %s", tool_output)
                    self.captured_tool_outputs.append(response)

    def start_trace(self, trace_id: Optional[str] = None) -> None:
        """No-op."""

    def end_trace(
        self,
        trace_id: Optional[str] = None,
        trace_map: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        """No-op."""

    async def async_event_gen(self) -> AsyncGenerator[CallbackEvent, None]:
        while not self._aqueue.empty() or not self.is_done:
            try:
                yield await asyncio.wait_for(self._aqueue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                pass
