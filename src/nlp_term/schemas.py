from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Domain = Literal["graduation", "notices", "academic_calendar", "dining", "shuttle"]


class RawSource(BaseModel):
    source_id: str
    label: int = Field(ge=0, le=4)
    domain: Domain
    url: str
    fetched_at: str
    content_type: str
    raw_path: str
    status_code: int | None = None
    checksum: str


class SourceVerification(BaseModel):
    source_id: str
    official_chain_ok: bool
    parser_name: str
    parser_version: str
    evidence: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    verified_at: str


class KnowledgeDoc(BaseModel):
    doc_id: str
    label: int = Field(ge=0, le=4)
    domain: Domain
    title: str
    body: str
    date: str | None = None
    source_url: str
    source_id: str
    section: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClassificationExample(BaseModel):
    question: str
    label: int = Field(ge=0, le=4)
    source_doc_id: str | None = None
    generation_method: Literal["manual", "template", "augmented", "dry_run"] = "dry_run"
    validated: bool = False


class ClassificationInput(BaseModel):
    question: str


class ClassificationOutput(BaseModel):
    question: str
    label: int = Field(ge=0, le=4)


class ChatInput(BaseModel):
    user: str


class ChatOutput(BaseModel):
    user: str
    model: str


class RealtimeOutput(BaseModel):
    user: str
    model: str
