from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class VectorStoreNode(BaseModel):
    node_id: str
    text: str
    metadata: Dict[str, Any] = {}
    embedding: Optional[List[float]] = None
