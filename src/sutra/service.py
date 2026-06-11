from __future__ import annotations

import logging
from typing import Protocol

from sutra.config import Config, load_config
from sutra.documents import load_documents
from sutra.llama import LlamaClient
from sutra.models import Answer, LlamaResult, Message
from sutra.prompts import render_prompt
from sutra.retrieval import retrieve
from sutra.tools import dispatch, get_tool_definitions

logger = logging.getLogger(__name__)


class ChatClient(Protocol):
    def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        tools: list[dict[str, object]] | None = None,
    ) -> LlamaResult:
        ...


def ask(
    question: str,
    *,
    workspace: str | Config,
    client: ChatClient | None = None,
    live: bool = False,
) -> Answer:
    """Ask a single question and return an Answer.

    The live flag is accepted for backward compatibility. Tool definitions are
    always injected; the model decides whether to call one.
    """
    config = workspace if isinstance(workspace, Config) else load_config(workspace)
    documents = load_documents(config)
    evidence = retrieve(question, documents, config)

    if not evidence.items:
        return Answer(
            answer="I do not have enough evidence in this workspace to answer.",
            evidence=[],
            workspace=config.workspace.name,
            model=config.runtime.model,
            backend=config.runtime.backend,
            trace={"status": "insufficient_evidence", "retrieved": 0},
        )

    prompt = render_prompt(question, evidence, config)
    llm = client or LlamaClient(config.runtime.base_url, timeout_seconds=config.runtime.timeout_seconds)

    tools = get_tool_definitions()
    result = llm.chat(
        prompt.messages,
        model=config.runtime.model,
        temperature=config.runtime.temperature,
        max_tokens=config.runtime.max_tokens,
        tools=tools or None,
    )

    called_tools: list[str] = []
    if tools and result.tool_calls:
        extra = []
        for tc in result.tool_calls:
            fresh = dispatch(tc.function_name, tc.function_arguments)
            if fresh:
                extra.extend(fresh)
                called_tools.append(tc.function_name)

        if extra:
            for item in extra:
                evidence.items.insert(0, item)
            prompt = render_prompt(question, evidence, config)
            result = llm.chat(
                prompt.messages,
                model=config.runtime.model,
                temperature=config.runtime.temperature,
                max_tokens=config.runtime.max_tokens,
            )
        else:
            disclaimer = "\n\n(Unable to fetch live data. Response is based on stored information.)"
            if result.content:
                result = LlamaResult(
                    content=result.content + disclaimer,
                    model=result.model,
                    usage=result.usage,
                    raw=result.raw,
                )

    return Answer(
        answer=result.content,
        evidence=evidence.items,
        workspace=config.workspace.name,
        model=result.model or config.runtime.model,
        backend=config.runtime.backend,
        usage=result.usage,
        trace={
            "status": "answered",
            "retrieved": len(evidence.items),
            "doc_ids": [item.id for item in evidence.items],
            "context_chars": len(prompt.context),
            "tools_called": called_tools,
        },
    )


def fallback_answer(question: str, *, workspace: str | Config) -> Answer:
    """Build a deterministic answer from retrieved evidence only."""
    config = workspace if isinstance(workspace, Config) else load_config(workspace)
    documents = load_documents(config)
    evidence = retrieve(question, documents, config)

    if not evidence.items:
        answer = "제공된 자료에서 확인할 수 있는 근거를 찾지 못했습니다."
    else:
        item = evidence.items[0]
        fact = _first_fact(item.text)
        source = item.source_url or item.source_name or item.id
        if item.source_url:
            answer = f"확인된 자료에 따르면 {fact} 자세한 내용은 {source}에서 확인하세요."
        else:
            answer = f"확인된 자료에 따르면 {fact} 출처는 {source}입니다."

    return Answer(
        answer=answer,
        evidence=evidence.items,
        workspace=config.workspace.name,
        model=config.runtime.model,
        backend=config.runtime.backend,
        trace={
            "status": "fallback",
            "retrieved": len(evidence.items),
            "doc_ids": [item.id for item in evidence.items],
        },
    )


def _first_fact(text: str) -> str:
    stripped = " ".join(text.split())
    if not stripped:
        return "관련 근거가 비어 있습니다."
    sentence_end = stripped.find(".")
    if 0 <= sentence_end < 180:
        return stripped[: sentence_end + 1]
    if len(stripped) <= 180:
        return stripped
    return stripped[:179].rstrip() + "..."


def chat(
    messages: list[Message] | list[dict[str, str]],
    *,
    workspace: str | Config,
    client: ChatClient | None = None,
) -> Answer:
    """Chat with context using the last user message as the question."""
    normalized = [
        message if isinstance(message, Message) else Message.model_validate(message)
        for message in messages
    ]
    user_messages = [message for message in normalized if message.role == "user"]
    if not user_messages:
        raise ValueError("chat requires at least one user message")
    return ask(user_messages[-1].content, workspace=workspace, client=client)
