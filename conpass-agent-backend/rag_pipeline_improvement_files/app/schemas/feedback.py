from typing import List, Literal, Optional

from pydantic import BaseModel


class FeedbackRequest(BaseModel):
    session_id: str
    message_id: str
    rating: Literal["thumbs_up", "thumbs_down"]
    comment: Optional[str] = None
    tool_used: Optional[str] = None
    result_contract_ids: Optional[List[int]] = None


class FeedbackResponse(BaseModel):
    status: str
    feedback_id: str
