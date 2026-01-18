from pydantic import BaseModel, Field
from typing import List

class ChatResponse(BaseModel):
    message: str = Field(..., description="Agent response in text format (do not embed image links in message)")
    image: List[str] = Field(default_factory=list, description="List of image URLs")
