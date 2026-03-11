from typing import List, Optional
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class URLNodePostprocessor(BaseNodePostprocessor):
    """Node post-processor to add a URL to the node metadata."""

    def _postprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> List[NodeWithScore]:
        """Post-process nodes to add a URL to the metadata."""
        for node in nodes:
            try:
                metadata = node.metadata
                contract_id = metadata.get("contract_id")
                contract_url = (
                    f"{settings.CONPASS_FRONTEND_BASE_URL}/contract/{contract_id}"
                )
                metadata["contract_url"] = contract_url

                if metadata.get("private"):
                    del metadata["private"]
                if metadata.get("directory_id"):
                    del metadata["directory_id"]
                if metadata.get("summary"):
                    del metadata["summary"]

            except Exception as e:
                logger.error(f"Error processing node: {e}")
                continue

        return nodes
