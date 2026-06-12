from __future__ import annotations

import json
import logging
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Protocol

from sutra.config import Config, load_config
from sutra.documents import load_documents
from sutra.llama import LlamaClient
from sutra.models import Answer, Evidence, EvidencePack, LlamaResult, Message, ToolCall
from sutra.prompts import get_current_time_str, render_prompt
from sutra.retrieval import retrieve
from sutra.tools import INTERNAL_TO_DISPLAY, dispatch, get_tool_definitions
from sutra.tracelog import TraceSource, append_chat_trace, default_trace_path

logger = logging.getLogger(__name__)

TOOL_ONLY_SYSTEM_INSTRUCTION = (
    "저장된 정보가 필요하면 search_knowledge_base를 호출하고, "
    "실시간 정보가 필요하면 해당 fetch 도구를 호출하세요."
)
INSUFFICIENT_EVIDENCE_ANSWER = "관련 정보를 확인할 수 있는 자료를 찾지 못했습니다. 충남대학교 공식 홈페이지를 확인해 주세요."


class ChatClient(Protocol):
    def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        tools: list[dict[str, object]] | None = None,
        tool_choice: dict[str, Any] | str | None = None,
    ) -> LlamaResult:
        ...


ROUTER_DOMAINS = {
    0: "graduation",
    1: "notices",
    2: "academic_calendar",
    3: "dining",
    4: "shuttle",
}
ROUTER_FORCED_TOOLS = {
    "dining": "fetch_cafeteria_menu",
    "notices": "fetch_recent_notices",
}
CLASSIFIER_MODEL_PATH = Path("model/classifier.joblib")


def route_question(question: str, config: Config) -> tuple[str, str | None, int | None]:
    """Route a question to a domain and optional forced live tool."""
    label = _predict_router_label(question, config=config)
    routed_domain = ROUTER_DOMAINS.get(label, "unknown")
    forced_tool = ROUTER_FORCED_TOOLS.get(routed_domain)
    return routed_domain, forced_tool, label


def ask(
    question: str,
    *,
    workspace: str | Config,
    client: ChatClient | None = None,
    live: bool = False,
    mode: Literal["default", "tool_only", "router"] = "default",
    trace_source: TraceSource | None = None,
    trace_path: str | Path | None = None,
) -> Answer:
    """Ask a single question and return an Answer.

    The live flag is accepted for backward compatibility. Tool definitions are
    always injected; the model decides whether to call one.
    """
    started = time.perf_counter()
    config = workspace if isinstance(workspace, Config) else load_config(workspace)
    if mode == "tool_only":
        return _ask_tool_only(question, config=config, client=client)
    if mode == "router":
        return _ask_router(
            question,
            config=config,
            client=client,
            trace_source=trace_source,
            trace_path=trace_path,
            started=started,
        )
    trace_file = Path(trace_path) if trace_path is not None else default_trace_path(config.root)

    documents = load_documents(config)
    evidence = retrieve(question, documents, config)

    if not evidence.items:
        answer = Answer(
            answer=_public_answer_text(INSUFFICIENT_EVIDENCE_ANSWER),
            evidence=[],
            workspace=config.workspace.name,
            model=config.runtime.model,
            backend=config.runtime.backend,
            trace={"status": "insufficient_evidence", "retrieved": 0},
        )
        _append_trace_if_requested(
            trace_source,
            trace_file,
            question=question,
            answer=answer.answer,
            evidence=[],
            tools_called=[],
            tool_args=[],
            mode="insufficient_evidence",
            started=started,
            usage=None,
            error=None,
        )
        return answer

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
    tool_args: list[dict[str, Any]] = []
    if tools and result.tool_calls:
        extra = []
        for tc in result.tool_calls:
            called_tools.append(tc.function_name)
            tool_args.append(_tool_arguments_dict(tc))
            fresh = dispatch(tc.function_name, tc.function_arguments)
            if fresh:
                extra.extend(fresh)

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
            disclaimer = "\n\n(실시간 정보를 가져오지 못해 저장된 자료를 기준으로 답변했습니다.)"
            if result.content:
                result = LlamaResult(
                    content=result.content + disclaimer,
                    model=result.model,
                    usage=result.usage,
                    raw=result.raw,
                )

    answer = Answer(
        answer=_public_answer_text(result.content),
        evidence=evidence.items,
        workspace=config.workspace.name,
        model=result.model or config.runtime.model,
        backend=config.runtime.backend,
        usage=result.usage,
        trace={
            "status": "answered",
            "retrieved": len(evidence.items),
            "doc_ids": [item.id for item in evidence.items],
            "doc_scores": [item.score for item in evidence.items],
            "context_chars": len(prompt.context),
            "tools_called": called_tools,
            "tool_args": tool_args,
        },
    )
    _append_trace_if_requested(
        trace_source,
        trace_file,
        question=question,
        answer=answer.answer,
        evidence=answer.evidence,
        tools_called=called_tools,
        tool_args=tool_args,
        mode="tool" if called_tools else "llm",
        started=started,
        usage=answer.usage,
        error=None,
    )
    return answer


def _ask_router(
    question: str,
    *,
    config: Config,
    client: ChatClient | None = None,
    trace_source: TraceSource | None = None,
    trace_path: str | Path | None = None,
    started: float | None = None,
) -> Answer:
    started = time.perf_counter() if started is None else started
    trace_file = Path(trace_path) if trace_path is not None else default_trace_path(config.root)
    routed_domain, forced_tool, label = route_question(question, config)
    classifier_fallback = label is None

    documents = load_documents(config)
    evidence = retrieve(question, documents, config)

    if not evidence.items and forced_tool is None:
        answer = Answer(
            answer=_public_answer_text(INSUFFICIENT_EVIDENCE_ANSWER),
            evidence=[],
            workspace=config.workspace.name,
            model=config.runtime.model,
            backend=config.runtime.backend,
            trace={
                "status": "insufficient_evidence",
                "retrieved": 0,
                "routed_domain": routed_domain,
                "forced_tool": forced_tool,
                "tools_called": [],
                "classifier_fallback": classifier_fallback,
            },
        )
        _append_trace_if_requested(
            trace_source,
            trace_file,
            question=question,
            answer=answer.answer,
            evidence=[],
            tools_called=[],
            tool_args=[],
            mode="router_insufficient_evidence",
            started=started,
            usage=None,
            error=None,
            extra={
                "routed_domain": routed_domain,
                "forced_tool": forced_tool,
                "classifier_fallback": classifier_fallback,
            },
        )
        return answer

    llm = client or LlamaClient(config.runtime.base_url, timeout_seconds=config.runtime.timeout_seconds)
    called_tools: list[str] = []
    tool_args: list[dict[str, Any]] = []

    if forced_tool is None:
        prompt = render_prompt(question, evidence, config)
        result = llm.chat(
            prompt.messages,
            model=config.runtime.model,
            temperature=config.runtime.temperature,
            max_tokens=config.runtime.max_tokens,
        )
    else:
        tools = get_tool_definitions()
        result = llm.chat(
            _render_router_tool_request_messages(question, config),
            model=config.runtime.model,
            temperature=config.runtime.temperature,
            max_tokens=min(config.runtime.max_tokens, 256),
            tools=tools or None,
            tool_choice=_forced_tool_choice(forced_tool),
        )
        extra: list[Evidence] = []
        if result.tool_calls:
            for tc in result.tool_calls:
                called_tools.append(tc.function_name)
                tool_args.append(_tool_arguments_dict(tc))
                if tc.function_name != forced_tool:
                    logger.warning(
                        "Router forced %s but model returned %s; ignoring tool evidence",
                        forced_tool,
                        tc.function_name,
                    )
                    continue
                fresh = dispatch(tc.function_name, tc.function_arguments)
                if fresh:
                    extra.extend(fresh)

        if extra:
            evidence.items = list(extra)
            prompt = render_prompt(question, evidence, config)
            result = llm.chat(
                prompt.messages,
                model=config.runtime.model,
                temperature=config.runtime.temperature,
                max_tokens=config.runtime.max_tokens,
            )
        else:
            # Forced tool produced no fresh live evidence. Re-search WITH the
            # snapshot/fallback-only domains (notices) that general search excludes,
            # so the indexed snapshot can still answer. dining was removed from the
            # corpus entirely, so it stays empty here ("확인 불가").
            fallback_pack = retrieve(question, documents, config, exclude_domains=set())
            if fallback_pack.items:
                evidence.items = list(fallback_pack.items)
            if not evidence.items:
                prompt = render_prompt(question, evidence, config)
                result = LlamaResult(
                    content="실시간 조회에 실패했고 저장된 자료에서도 관련 정보를 찾지 못했습니다. 충남대학교 공식 홈페이지를 확인해 주세요.",
                    model=config.runtime.model,
                )
            else:
                prompt = render_prompt(question, evidence, config)
                fallback_result = llm.chat(
                    prompt.messages,
                    model=config.runtime.model,
                    temperature=config.runtime.temperature,
                    max_tokens=config.runtime.max_tokens,
                )
                result = LlamaResult(
                    content=(
                        fallback_result.content
                        + "\n\n(실시간 정보를 가져오지 못해 저장된 자료를 기준으로 답변했습니다.)"
                    ),
                    model=fallback_result.model,
                    usage=fallback_result.usage,
                    raw=fallback_result.raw,
                )

    answer = Answer(
        answer=_public_answer_text(result.content),
        evidence=evidence.items,
        workspace=config.workspace.name,
        model=result.model or config.runtime.model,
        backend=config.runtime.backend,
        usage=result.usage,
        trace={
            "status": "answered",
            "retrieved": len(evidence.items),
            "doc_ids": [item.id for item in evidence.items],
            "doc_scores": [item.score for item in evidence.items],
            "context_chars": len(prompt.context),
            "routed_domain": routed_domain,
            "forced_tool": forced_tool,
            "tools_called": called_tools,
            "tool_args": tool_args,
            "classifier_fallback": classifier_fallback,
        },
    )
    _append_trace_if_requested(
        trace_source,
        trace_file,
        question=question,
        answer=answer.answer,
        evidence=answer.evidence,
        tools_called=called_tools,
        tool_args=tool_args,
        mode="router_tool" if called_tools else "router_llm",
        started=started,
        usage=answer.usage,
        error=None,
        extra={
            "routed_domain": routed_domain,
            "forced_tool": forced_tool,
            "classifier_fallback": classifier_fallback,
        },
    )
    return answer


def _forced_tool_choice(tool_name: str) -> dict[str, dict[str, str] | str]:
    return {"type": "function", "function": {"name": tool_name}}


def _resolve_classifier_model_path(config: Config | None = None) -> Path | None:
    candidates: list[tuple[str, Path]] = []
    if env_path := os.getenv("SUTRA_CLASSIFIER_PATH"):
        candidates.append(("env", Path(env_path).expanduser().resolve()))
    if config is not None:
        candidates.append(("workspace", (config.root / CLASSIFIER_MODEL_PATH).resolve()))
    repo_root = Path(__file__).resolve().parents[2]
    candidates.append(("repo", (repo_root / CLASSIFIER_MODEL_PATH).resolve()))
    candidates.append(("cwd", (Path.cwd() / CLASSIFIER_MODEL_PATH).resolve()))

    seen: set[Path] = set()
    for source, path in candidates:
        if path in seen:
            continue
        seen.add(path)
        if path.exists():
            logger.info("Router classifier path candidate %s exists: %s", source, path)
            return path
        logger.info("Router classifier path candidate %s missing: %s", source, path)

    logger.info("Router classifier model not found; falling back to RAG-only")
    return None


@lru_cache(maxsize=4)
def _load_classifier(model_path: Path):
    """Load the joblib classifier pipeline once per path (cached for batch runs)."""
    import joblib

    return joblib.load(model_path)


def _predict_router_label(question: str, *, config: Config | None = None) -> int | None:
    model_path = _resolve_classifier_model_path(config)
    if model_path is None:
        return None

    try:
        model = _load_classifier(model_path)
        label = int(model.predict([question])[0])
        logger.info("Router classifier prediction succeeded: label=%s", label)
        return label
    except Exception:
        logger.warning("Router classifier prediction failed; falling back to RAG-only", exc_info=True)
        return None


def _ask_tool_only(
    question: str,
    *,
    config: Config,
    client: ChatClient | None = None,
) -> Answer:
    llm = client or LlamaClient(config.runtime.base_url, timeout_seconds=config.runtime.timeout_seconds)
    tools = get_tool_definitions(include_knowledge_base=True)
    messages = _render_tool_only_messages(question, config)
    result = llm.chat(
        messages,
        model=config.runtime.model,
        temperature=config.runtime.temperature,
        max_tokens=config.runtime.max_tokens,
        tools=tools or None,
    )

    called_tools: list[str] = []
    evidence_items = []
    context = ""
    if tools and result.tool_calls:
        for tc in result.tool_calls:
            called_tools.append(tc.function_name)
            fresh = dispatch(tc.function_name, tc.function_arguments, workspace=config)
            if fresh:
                evidence_items.extend(fresh)

        if called_tools:
            evidence = EvidencePack(question=question, items=evidence_items)
            prompt = render_prompt(question, evidence, config)
            context = prompt.context
            result = llm.chat(
                prompt.messages,
                model=config.runtime.model,
                temperature=config.runtime.temperature,
                max_tokens=config.runtime.max_tokens,
            )
            if not result.content:
                result = LlamaResult(
                    content=INSUFFICIENT_EVIDENCE_ANSWER,
                    model=result.model,
                    usage=result.usage,
                    raw=result.raw,
                )

    return Answer(
        answer=_public_answer_text(result.content),
        evidence=evidence_items,
        workspace=config.workspace.name,
        model=result.model or config.runtime.model,
        backend=config.runtime.backend,
        usage=result.usage,
        trace={
            "status": "answered",
            "retrieved": len(evidence_items),
            "doc_ids": [item.id for item in evidence_items],
            "context_chars": len(context),
            "tools_called": called_tools,
        },
    )


def _render_tool_only_messages(question: str, config: Config) -> list[Message]:
    system = config.prompts.system.read_text(encoding="utf-8").strip()
    system = f"{system}\n\n{TOOL_ONLY_SYSTEM_INSTRUCTION}"
    user = (
        f"Workspace: {config.workspace.name}\n"
        f"Timezone: {config.workspace.timezone}\n"
        f"Current Time: {get_current_time_str(config.workspace.timezone)}\n\n"
        f"Question:\n{question}"
    )
    return [
        Message(role="system", content=system),
        Message(role="user", content=user),
    ]


def _render_router_tool_request_messages(question: str, config: Config) -> list[Message]:
    system = config.prompts.system.read_text(encoding="utf-8").strip()
    user = (
        f"Workspace: {config.workspace.name}\n"
        f"Timezone: {config.workspace.timezone}\n"
        f"Current Time: {get_current_time_str(config.workspace.timezone)}\n\n"
        f"Question:\n{question}"
    )
    return [
        Message(role="system", content=system),
        Message(role="user", content=user),
    ]


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
        answer=_public_answer_text(answer),
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


def _tool_arguments_dict(tool_call: ToolCall) -> dict[str, Any]:
    try:
        parsed = json.loads(tool_call.function_arguments or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _public_answer_text(text: str) -> str:
    for internal, display in INTERNAL_TO_DISPLAY.items():
        text = text.replace(internal, display)
    return text


def _append_trace_if_requested(
    source: TraceSource | None,
    path: Path,
    *,
    question: str,
    answer: str,
    evidence: list[Evidence],
    tools_called: list[str],
    tool_args: list[dict[str, Any]],
    mode: str,
    started: float,
    usage: dict[str, Any] | None,
    error: str | None,
    extra: dict[str, Any] | None = None,
) -> None:
    if source is None:
        return
    append_chat_trace(
        path,
        source=source,
        question=question,
        answer=answer,
        evidence=evidence,
        tools_called=tools_called,
        tool_args=tool_args,
        mode=mode,
        latency_ms=int((time.perf_counter() - started) * 1000),
        usage=usage,
        error=error,
        extra=extra,
    )


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
