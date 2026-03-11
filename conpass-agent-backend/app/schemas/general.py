from typing import Optional, Literal, Any
from pydantic import BaseModel
from pydantic import Field


class GeneralResponse(BaseModel):
    status: Literal["success", "error"] = Field(
        ..., description="Status of the response"
    )
    description: Optional[str] = Field(None, description="Description of the response")
    data: Optional[Any] = Field(None, description="Data of the response")
