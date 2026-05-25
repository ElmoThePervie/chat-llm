from datetime import datetime

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=32000)


class MessageOut(BaseModel):
    id: int
    chat_id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
