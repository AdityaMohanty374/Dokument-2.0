from datetime import datetime
from pydantic import BaseModel


class ChatRequest(BaseModel):
    conversation_id: str
    message: str


class ConversationCreate(BaseModel):
    title: str | None = None


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserOut(BaseModel):
    id: str
    email: str
    name: str | None
    picture: str | None

    class Config:
        from_attributes = True
