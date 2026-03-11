from typing import Optional, Dict, Any


def get_document_id(payload: Dict[str, Any]) -> Optional[int]:
    """Extract document ID from payload, trying multiple fields.

    In LlamaIndex, chunks reference their parent document via ref_doc_id.
    The doc_id field is also used but may vary. document_id is less common.
    """
    # Try ref_doc_id first (this is what LlamaIndex uses for chunk->document reference)
    doc_id = payload.get("contract_id")
    if doc_id is not None:
        return int(doc_id)
    return None
