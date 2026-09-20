from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    display_name: str = Field(default="", max_length=120)
    locale: str = Field(default="en", pattern="^(en|ar)$")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_name: str | None = Field(default=None, max_length=120)


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(ORMModel):
    id: str
    email: str
    display_name: str
    locale: str
    is_email_verified: bool


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    kind: str = Field(default="personal", pattern="^(personal|shared)$")


class WorkspaceOut(ORMModel):
    id: str
    owner_id: str
    name: str
    slug: str
    description: str | None
    kind: str
    created_at: datetime
    role: str = "viewer"


class DocumentOut(ORMModel):
    id: str
    workspace_id: str
    folder_id: str | None
    original_filename: str
    title: str
    mime_type: str
    file_size: int
    status: str
    processing_progress: int
    page_count: int | None
    error_message: str | None = None
    created_at: datetime


class SearchRequest(BaseModel):
    workspace_id: str
    query: str = Field(min_length=1, max_length=4000)
    document_ids: list[str] = Field(default_factory=list, max_length=100)
    folder_id: str | None = None
    tag_ids: list[str] = Field(default_factory=list, max_length=50)
    exact_phrase: bool = False
    limit: int = Field(default=12, ge=1, le=50)


class SearchHit(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    page_number: int | None
    section_title: str | None
    excerpt: str
    score: float
    semantic_score: float
    keyword_score: float


class ConversationCreate(BaseModel):
    workspace_id: str
    title: str = Field(default="New conversation", max_length=240)
    document_ids: list[str] = Field(default_factory=list, max_length=100)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    document_ids: list[str] = Field(default_factory=list, max_length=100)
    language: str = Field(default="auto", pattern="^(auto|en|ar)$")


class FlashcardReviewRequest(BaseModel):
    rating: str = Field(pattern="^(again|hard|good|easy)$")
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)
