import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database import Base


def gen_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    google_id = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversations = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    title = Column(String, default="New conversation")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "Message", back_populates="conversation",
        cascade="all, delete-orphan", order_by="Message.created_at"
    )
    documents = relationship(
        "Document", back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_conversations_user_updated", "user_id", "updated_at"),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    conversation_id = Column(
        UUID(as_uuid=False), ForeignKey("conversations.id"), nullable=False
    )
    role = Column(String, nullable=False)  # "system" | "user" | "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    conversation_id = Column(
        UUID(as_uuid=False), ForeignKey("conversations.id"), nullable=False
    )
    filename = Column(String, nullable=False)
    storage_key = Column(String, nullable=False)  # key/path in R2 bucket
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="documents")
