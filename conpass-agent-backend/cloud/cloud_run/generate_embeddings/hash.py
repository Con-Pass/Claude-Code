import hashlib
import json
from typing import Any, Dict


def compute_document_hash(text: str, metadata: Dict[str, Any]) -> str:
    """
    Compute SHA256 hash of document text and metadata combined.

    Args:
        text: Document text content
        metadata: Document metadata dictionary

    Returns:
        Hexadecimal hash string
    """
    # Sort keys for consistent hashing
    combined = json.dumps({"text": text, "metadata": metadata}, sort_keys=True)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
