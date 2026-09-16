from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .base import UUIDMixin, TimestampMixin
from ..db import Base


class Conversation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "conversations"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(240), default="New conversation", index=True)
    scope_type: Mapped[str] = mapped_column(String(30), default="workspace")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class ConversationDocument(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "conversation_documents"
    __table_args__ = (UniqueConstraint("conversation_id", "document_id", name="uq_conversation_document"),)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)


class Message(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "messages"
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), index=True)
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="complete", index=True)
    model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)


class MessageCitation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "message_citations"
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("document_chunks.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source_excerpt: Mapped[str] = mapped_column(Text)
    ordinal: Mapped[int] = mapped_column(Integer)


class Note(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "notes"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    content_markdown: Mapped[str] = mapped_column(Text, default="")
    source_links: Mapped[list] = mapped_column(JSON, default=list)


class SavedPrompt(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "saved_prompts"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    prompt: Mapped[str] = mapped_column(Text)
