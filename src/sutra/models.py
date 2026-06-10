from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class Document(BaseModel):
    id: str
    text: str
    title: str = ""
    source_url: str | None = None
    source_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScoredDocument(BaseModel):
    document: Document
    score: float


class Evidence(BaseModel):
    id: str
    text: str
    title: str = ""
    source_url: str | None = None
    source_name: str | None = None
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Answer(BaseModel):
    answer: str
    evidence: list[Evidence] = Field(default_factory=list)
    workspace: str
    model: str | None = None
    backend: str | None = None
    usage: dict[str, Any] | None = None
    trace: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    id: str
    type: str = "function"
    function_name: str
    function_arguments: str = "{}"


class LlamaResult(BaseModel):
    content: str
    model: str | None = None
    usage: dict[str, Any] | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[ToolCall] = Field(default_factory=list)


class EvidencePack(BaseModel):
    question: str
    items: list[Evidence] = Field(default_factory=list)


class PromptBundle(BaseModel):
    messages: list[Message]
    context: str
