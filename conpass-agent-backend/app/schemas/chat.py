import json
from app.core.logging_config import get_logger
import os
from enum import Enum
from typing import Any, Dict, List, Optional

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.schema import NodeWithScore
from pydantic import BaseModel, Field, field_validator, ConfigDict
from pydantic.alias_generators import to_camel

from app.core.config import Settings
from app.core.environment_flags import is_development
from app.schemas.upload import DocumentFile

logger = get_logger(__name__)

settings = Settings()


class AnnotationFileData(BaseModel):
    files: List[DocumentFile] = Field(
        default=[],
        description="List of files",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "files": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "file_name": "example.pdf",
                        "content_type": "application/pdf",
                        "file_url": "https://www.xyz.con-pass.jp/files/550e8400-e29b-41d4-a716-446655440000/example.pdf",
                        "extracted_text_url": "https://www.xyz.con-pass.jp/extracted/550e8400-e29b-41d4-a716-446655440000.txt",
                        "token_count": 150,
                    }
                ]
            }
        },
        alias_generator=to_camel,
    )

    @staticmethod
    def _get_url_llm_content(file: DocumentFile) -> Optional[str]:
        """
        Get file URL content for LLM from DocumentFile.
        Uses extracted_text_url from GCS storage (CDN URL to extracted text).
        """
        # Use extracted text URL from GCS storage
        if file.extracted_text_url:
            return f"Extracted Text URL: {file.extracted_text_url}\n"

        return None

    @classmethod
    def _get_file_content(cls, file: DocumentFile) -> str:
        """
        Construct content for LLM from the file metadata.
        Updated to work with new DocumentFile schema that uses GCS/CDN storage.
        """
        default_content = f"=====File: {file.file_name}=====\n"

        # Include file ID
        if file.id:
            default_content += f"File ID: {file.id}\n"

        # Include content type if available
        if file.content_type:
            default_content += f"Content Type: {file.content_type}\n"

        # Include file URL if it's available (CDN URL from GCS)
        url_content = cls._get_url_llm_content(file)
        if url_content:
            default_content += url_content

        # Include token count if available
        if file.token_count is not None:
            default_content += f"Token Count: {file.token_count}\n"

        return default_content

    def to_llm_content(self) -> Optional[str]:
        file_contents = [self._get_file_content(file) for file in self.files]
        if len(file_contents) == 0:
            return None
        return "Use data from following files content\n" + "\n".join(file_contents)


class AgentAnnotation(BaseModel):
    agent: str
    text: str


class ArtifactAnnotation(BaseModel):
    toolCall: Dict[str, Any]
    toolOutput: Dict[str, Any]


class Annotation(BaseModel):
    type: str
    data: AnnotationFileData | List[str] | AgentAnnotation | ArtifactAnnotation

    def to_content(self) -> Optional[str]:
        if self.type == "document_file" and isinstance(self.data, AnnotationFileData):
            return self.data.to_llm_content()
        # elif self.type == "image":
        #     raise NotImplementedError("Use image file is not supported yet!")
        # else:
        #     logger.warning(
        #         f"The annotation {self.type} is not supported for generating context content"
        #     )
        raise NotImplementedError(
            f"The annotation {self.type} is not supported for generating context content"
        )


class Message(BaseModel):
    role: MessageRole
    content: str
    annotations: List[Annotation] | None = None
    parts: Optional[List[Dict[str, Any]]] = (
        None  # Client payload format (e.g., [{"type": "text", "text": "..."}])
    )


class SessionType(str, Enum):
    CONPASS_ONLY = "conpass-only"
    GENERAL = "general"
    MANAGEMENT = "management"


class SessionData(BaseModel):
    type: SessionType
    chat_id: Optional[str] = None  # For continuing existing chats


class ChatData(BaseModel):
    messages: List[Message]
    data: SessionData

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "messages": [
                    {
                        "role": "user",
                        "content": "Fetch me all contracts that end in December 2025",
                    }
                ],
                "data": {"type": "conpass-only"},
            }
        }
    )

    @field_validator("messages")
    @classmethod
    def messages_must_not_be_empty(cls, v):
        if len(v) == 0:
            raise ValueError("Messages must not be empty")
        return v

    @field_validator("data")
    @classmethod
    def data_must_be_valid(cls, v):
        if v.type not in SessionType:
            raise ValueError("Data must be valid")
        return v

    def get_session_type(self) -> SessionType:
        return self.data.type

    def get_last_message_content(self) -> str:
        """
        Get the content of the last message along with the data content from all user messages.
        Files from the current message are separated from files in previous messages to help
        the agent distinguish between "this file" vs "all files" scenarios.
        """
        if is_development():
            if len(self.messages) == 0:
                raise ValueError("There is not any message in the chat")

            last_message = self.messages[-1]
            message_content = last_message.content

            # Separate current message annotations from historical ones
            current_annotation_contents: List[str] = []
            historical_annotation_contents: List[str] = []

            for i, message in enumerate(self.messages):
                if message.role == MessageRole.USER and message.annotations is not None:
                    annotation_contents = filter(
                        None,
                        [annotation.to_content() for annotation in message.annotations],
                    )
                    annotation_list = list(annotation_contents)

                    if i == len(self.messages) - 1:
                        # Current message (last message)
                        current_annotation_contents.extend(annotation_list)
                    else:
                        # Historical messages
                        historical_annotation_contents.extend(annotation_list)

            # Structure the content with clear markers
            if current_annotation_contents or historical_annotation_contents:
                annotation_text_parts: List[str] = []

                if current_annotation_contents:
                    annotation_text_parts.append(
                        "=== Files uploaded in this message ===\n"
                        + "\n".join(current_annotation_contents)
                    )

                if historical_annotation_contents:
                    annotation_text_parts.append(
                        "=== Files from previous messages in this session ===\n"
                        + "\n".join(historical_annotation_contents)
                    )

                if annotation_text_parts:
                    message_content = f"{message_content}\n\n" + "\n\n".join(
                        annotation_text_parts
                    )

            return message_content
        else:
            if len(self.messages) == 0:
                raise ValueError("There is not any message in the chat")

            last_message = self.messages[-1]
            message_content = last_message.content

            # Collect annotation contents from all user messages
            all_annotation_contents: List[str] = []
            for message in self.messages:
                if message.role == MessageRole.USER and message.annotations is not None:
                    annotation_contents = filter(
                        None,
                        [annotation.to_content() for annotation in message.annotations],
                    )
                    all_annotation_contents.extend(annotation_contents)

            # Add all annotation contents if any exist
            if len(all_annotation_contents) > 0:
                annotation_text = "\n".join(all_annotation_contents)
                message_content = f"{message_content}\n{annotation_text}"

            return message_content

    def _get_agent_messages(self, max_messages: int = 10) -> List[str]:
        """
        Construct agent messages from the annotations in the chat messages
        """
        agent_messages = []
        for message in self.messages:
            if (
                message.role == MessageRole.ASSISTANT
                and message.annotations is not None
            ):
                for annotation in message.annotations:
                    if annotation.type == "agent" and isinstance(
                        annotation.data, AgentAnnotation
                    ):
                        text = annotation.data.text
                        agent_messages.append(
                            f"\nAgent: {annotation.data.agent}\nsaid: {text}\n"
                        )
                        if len(agent_messages) >= max_messages:
                            break
        return agent_messages

    def _get_latest_code_artifact(self) -> Optional[str]:
        """
        Get latest code artifact from annotations to append to the user message
        """
        for message in reversed(self.messages):
            if (
                message.role == MessageRole.ASSISTANT
                and message.annotations is not None
            ):
                for annotation in message.annotations:
                    # type is tools and has `toolOutput` attribute
                    if annotation.type == "tools" and isinstance(
                        annotation.data, ArtifactAnnotation
                    ):
                        tool_output = annotation.data.toolOutput
                        if tool_output and not tool_output.get("isError", False):
                            output = tool_output.get("output", {})
                            if isinstance(output, dict) and output.get("code"):
                                return output.get("code")
                            else:
                                return None
        return None

    def get_history_messages(
        self,
        include_agent_messages: bool = False,
        include_code_artifact: bool = True,
    ) -> List[ChatMessage]:
        """
        Get the history messages, including tool outputs from annotations
        """
        chat_messages = []
        if is_development():
            # Exclude the last message: it is passed separately as user_msg with
            # full content (including file annotations). Including it here with
            # only message.content would create a duplicate user turn—short then
            # full—and the model may treat the short one as the request and
            # ignore file IDs (e.g. respond "該当する契約は見つかりませんでした"
            # without calling get_file_content_tool / document_diffing_tool).
            for message in self.messages[:-1]:
                # Add the basic message
                chat_messages.append(
                    ChatMessage(role=message.role, content=message.content)
                )

                # If this is an assistant message with tool outputs, include them
                if (
                    message.role == MessageRole.ASSISTANT
                    and message.annotations is not None
                ):
                    tool_outputs = []
                    for annotation in message.annotations:
                        if annotation.type == "tools" and isinstance(
                            annotation.data, ArtifactAnnotation
                        ):
                            tool_output_data = annotation.data.toolOutput
                            tool_call_data = annotation.data.toolCall

                            if tool_output_data and not tool_output_data.get(
                                "isError", False
                            ):
                                tool_name = tool_call_data.get("name", "unknown_tool")
                                output = tool_output_data.get("output", {})

                                # Format the tool output for the LLM with proper JSON formatting
                                try:
                                    output_str = json.dumps(
                                        output, indent=2, ensure_ascii=False
                                    )
                                except (TypeError, ValueError):
                                    output_str = str(output)

                                tool_output_text = f"\n[Tool Call Result]\nTool: {tool_name}\nOutput:\n{output_str}\n"
                                tool_outputs.append(tool_output_text)

                    # If we found tool outputs, add them as a separate message
                    if tool_outputs:
                        tool_context_message = ChatMessage(
                            role=MessageRole.ASSISTANT,
                            content="Tool outputs from previous turn:\n"
                            + "\n".join(tool_outputs),
                        )
                        chat_messages.append(tool_context_message)
        else:
            # Process all messages except the last one
            for message in self.messages[:-1]:
                # Add the basic message
                chat_messages.append(
                    ChatMessage(role=message.role, content=message.content)
                )

                # If this is an assistant message with tool outputs, include them
                if (
                    message.role == MessageRole.ASSISTANT
                    and message.annotations is not None
                ):
                    tool_outputs = []
                    for annotation in message.annotations:
                        if annotation.type == "tools" and isinstance(
                            annotation.data, ArtifactAnnotation
                        ):
                            tool_output_data = annotation.data.toolOutput
                            tool_call_data = annotation.data.toolCall

                            if tool_output_data and not tool_output_data.get(
                                "isError", False
                            ):
                                tool_name = tool_call_data.get("name", "unknown_tool")
                                output = tool_output_data.get("output", {})

                                # Format the tool output for the LLM with proper JSON formatting
                                try:
                                    output_str = json.dumps(
                                        output, indent=2, ensure_ascii=False
                                    )
                                except (TypeError, ValueError):
                                    output_str = str(output)

                                tool_output_text = f"\n[Tool Call Result]\nTool: {tool_name}\nOutput:\n{output_str}\n"
                                tool_outputs.append(tool_output_text)

                    # If we found tool outputs, add them as a separate message
                    if tool_outputs:
                        tool_context_message = ChatMessage(
                            role=MessageRole.ASSISTANT,
                            content="Tool outputs from previous turn:\n"
                            + "\n".join(tool_outputs),
                        )
                        chat_messages.append(tool_context_message)

        if include_agent_messages:
            agent_messages = self._get_agent_messages(max_messages=5)
            if len(agent_messages) > 0:
                message = ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content="Previous agent events: \n" + "\n".join(agent_messages),
                )
                chat_messages.append(message)
        if include_code_artifact:
            latest_code_artifact = self._get_latest_code_artifact()
            if latest_code_artifact:
                message = ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=f"The existing code is:\n```\n{latest_code_artifact}\n```",
                )
                chat_messages.append(message)
        return chat_messages

    def is_last_message_from_user(self) -> bool:
        return self.messages[-1].role == MessageRole.USER

    def get_chat_document_ids(self) -> List[str]:
        """
        Get the document IDs from the chat messages.

        Note: The new DocumentFile schema doesn't include a 'refs' field.
        Document IDs are now identified by the file 'id' field.
        Returns a list of unique file IDs.
        """
        document_ids: List[str] = []
        uploaded_files = self.get_document_files()
        for _file in uploaded_files:
            # Use file ID as document ID (new schema)
            if _file.id:
                document_ids.append(_file.id)
            # Legacy support: check for refs attribute if it exists (backward compatibility)
            # refs = getattr(_file, "refs", None)
            # if refs is not None:
            #     if isinstance(refs, list):
            #         document_ids.extend(refs)
            #     else:
            #         document_ids.append(str(refs))
        return list(set(document_ids))

    def get_document_files(self) -> List[DocumentFile]:
        """
        Get the uploaded files from the chat data
        """
        uploaded_files = []
        for message in self.messages:
            if message.role == MessageRole.USER and message.annotations is not None:
                for annotation in message.annotations:
                    if annotation.type == "document_file" and isinstance(
                        annotation.data, AnnotationFileData
                    ):
                        uploaded_files.extend(annotation.data.files)
        return uploaded_files


class SourceNodes(BaseModel):
    id: str
    metadata: Dict[str, Any]
    score: Optional[float]
    text: str
    url: Optional[str]

    @classmethod
    def from_source_node(cls, source_node: NodeWithScore):
        metadata = source_node.node.metadata
        url = cls.get_url_from_metadata(metadata)

        return cls(
            id=source_node.node.node_id,
            metadata=metadata,
            score=source_node.score,
            text=source_node.node.text,  # type: ignore
            url=url,
        )

    @classmethod
    def get_url_from_metadata(cls, metadata: Dict[str, Any]) -> Optional[str]:
        url_prefix = settings.FILESERVER_URL_PREFIX
        if not url_prefix:
            logger.warning(
                "Warning: FILESERVER_URL_PREFIX not set in environment variables. Can't use file server"
            )
        file_name = metadata.get("file_name")

        if file_name and url_prefix:
            # file_name exists and file server is configured
            pipeline_id = metadata.get("pipeline_id")
            if pipeline_id:
                # file is from LlamaCloud
                file_name = f"{pipeline_id}${file_name}"
                return f"{url_prefix}/output/llamacloud/{file_name}"
            is_private = metadata.get("private", "false") == "true"
            if is_private:
                # file is a private upload
                return f"{url_prefix}/output/uploaded/{file_name}"
            # file is from calling the 'generate' script
            # Get the relative path of file_path to data_dir
            file_path = metadata.get("file_path")
            data_dir = os.path.abspath(settings.DATA_DIR)
            if file_path and data_dir:
                relative_path = os.path.relpath(file_path, data_dir)
                return f"{url_prefix}/data/{relative_path}"
        # fallback to URL in metadata (e.g. for websites)
        return metadata.get("URL")

    @classmethod
    def from_source_nodes(cls, source_nodes: List[NodeWithScore]):
        return [cls.from_source_node(node) for node in source_nodes]


class Result(BaseModel):
    result: Message
    nodes: List[SourceNodes]
