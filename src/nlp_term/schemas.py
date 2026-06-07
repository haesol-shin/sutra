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
    generation_method: Literal["manual", "template", "augmented", "self_consistency", "dry_run"] = "dry_run"
    validated: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class LabelAudit(BaseModel):
    question: str
    source_doc_id: str
    vote_labels: list[int] = Field(min_length=1)
    final_label: int = Field(ge=0, le=4)
    confidence: float = Field(ge=0.0, le=1.0)
    decision: Literal["accept", "review", "reject"]
    reviewer_override: int | None = Field(default=None, ge=0, le=4)


class QAExample(BaseModel):
    user: str
    model: str
    source_doc_id: str
    source_url: str
    label: int = Field(ge=0, le=4)
    validated: bool = False


class Task1HumanGoldExample(BaseModel):
    question: str
    label: int = Field(ge=0, le=4)
    source_doc_id: str | None = None
    difficulty: Literal["short", "natural", "ambiguous", "boundary", "typo"]
    ambiguous_reason: str | None = None
    annotator: str
    validated: bool = False


class Task2FactGoldExample(BaseModel):
    fact_id: str
    label: int = Field(ge=0, le=4)
    source_doc_id: str
    source_url: str
    claim: str
    evidence_quote: str
    answerable_scope: Literal["static", "fresh", "unknown"]


class Task2AnswerEvalGoldExample(BaseModel):
    user: str
    expected_fact_ids: list[str] = Field(min_length=1)
    must_not_claim: list[str] = Field(default_factory=list)
    naturalness_score: float | None = Field(default=None, ge=1.0, le=5.0)
    factuality_score: float | None = Field(default=None, ge=1.0, le=5.0)


class RetrievedDoc(BaseModel):
    doc_id: str
    score: float
    title: str
    source_url: str
    label: int = Field(ge=0, le=4)


class ModelCandidate(BaseModel):
    name: str
    task: Literal["task1", "task2", "task3"]
    max_params_b: float
    status: Literal["primary", "candidate", "cut", "reference"]
    reason: str
    source_url: str | None = None


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
