from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import chainlit as cl

from sutra.config import Config, load_config
from sutra.documents import load_documents
from sutra.errors import SutraError
from sutra.llama import EchoClient, LlamaClient, has_stream_tool_call_marker
from sutra.models import Evidence, EvidencePack, LlamaResult, Message, ToolCall
from sutra.prompts import render_prompt
from sutra.retrieval import retrieve
from sutra.service import (
    _forced_tool_choice,
    _render_router_tool_request_messages,
    route_question,
)
from sutra.tools import dispatch, get_tool_definitions
from sutra.tracelog import append_chat_trace, append_feedback, default_trace_path


logger = logging.getLogger(__name__)

_FEEDBACK_ACTION = "sutra_feedback"
_SOURCES_ACTION = "sutra_sources"
_SOURCES_SESSION_PREFIX = "sutra_sources:"
_FEEDBACK_SESSION_PREFIX = "sutra_feedback:"
_FEEDBACK_ANSWER_LIMIT = 200
RETRIEVAL_STEP_NAME = "🧠 Knowledge Base"
LIVE_LOOKUP_STEP_NAME = "🔍 Web Search"
UI_SCORE_REL_RATIO = float(os.environ.get("SUTRA_UI_SCORE_REL_RATIO", "0.4"))
UI_SCORE_ABS_FLOOR = float(os.environ.get("SUTRA_UI_SCORE_ABS_FLOOR", "0.0"))


class StreamOutcome:
    __slots__ = ("content", "marker_detected")

    def __init__(self, content: str, marker_detected: bool) -> None:
        self.content = content
        self.marker_detected = marker_detected


def _default_workspace_path() -> Path:
    return Path(__file__).resolve().parents[2] / "examples" / "cnu-campus" / "sutra.toml"


def _retrieval_summary(evidence_items: list[Evidence]) -> str:
    best_score = next((item.score for item in evidence_items if item.score is not None), None)
    document_label = "document" if len(evidence_items) == 1 else "documents"
    if best_score is None:
        return f"{len(evidence_items)} {document_label}"
    return f"{len(evidence_items)} {document_label} (best score {best_score:g})"


def _filter_source_evidence(
    evidence_items: list[Evidence],
    *,
    rel_ratio: float = UI_SCORE_REL_RATIO,
    abs_floor: float = UI_SCORE_ABS_FLOOR,
) -> tuple[list[Evidence], int]:
    scored = [item for item in evidence_items if item.score is not None]
    if not scored:
        return evidence_items, 0

    top_item = max(
        scored,
        key=lambda item: item.score if item.score is not None else float("-inf"),
    )
    top_score = top_item.score if top_item.score is not None else 0.0
    threshold = rel_ratio * top_score
    filtered = [
        item for item in evidence_items
        if item.score is None or (item.score >= threshold and item.score >= abs_floor)
    ]
    if not filtered and evidence_items:
        filtered = [top_item]
    return filtered, len(evidence_items) - len(filtered)


def _source_filter_summary(
    evidence_items: list[Evidence],
    shown_count: int,
    hidden_count: int,
) -> str:
    summary = _retrieval_summary(evidence_items)
    if hidden_count <= 0:
        return summary
    return f"{summary}\nshowing {shown_count} of {len(evidence_items)} (score filter)"


def _source_group_elements(group_name: str, evidence_items: list[Evidence]) -> list[cl.Text]:
    # The existing relative score filter is applied independently per source group.
    evidence_items, _ = _filter_source_evidence(evidence_items)
    if not evidence_items:
        return []

    elements: list[cl.Text] = []
    elements.append(cl.Text(name=group_name, content=group_name, display="side"))
    for i, ev in enumerate(evidence_items, 1):
        title = ev.title or "Untitled"
        source = ev.source_name or ev.source_url or ev.id
        date = _evidence_date(ev)
        lines = [f"Source: {source}"]
        if date:
            lines.append(f"Date: {date}")
        if ev.source_url:
            lines.append(f"URL: {ev.source_url}")
        lines.append(f"Excerpt: {_excerpt(ev.text, 500)}")
        elements.append(
            cl.Text(
                name=f"[{group_name} {i}] {title}",
                content="\n".join(lines),
                display="side",
            )
        )
    return elements


def _source_elements(
    knowledge_base_items: list[Evidence],
    web_search_items: list[Evidence] | None = None,
) -> list[cl.Text]:
    elements = _source_group_elements("Knowledge Base", knowledge_base_items)
    if web_search_items is not None:
        elements.extend(_source_group_elements("Web Search", web_search_items))
    return elements


def _sources_element(
    knowledge_base_items: list[Evidence],
    web_search_items: list[Evidence] | None = None,
) -> cl.Text | None:
    """Build a single collapsed '📚 Sources' side element.

    The element shows as one reference on the answer; the grouped source detail only
    opens in the side panel when the user clicks it (not auto-expanded inline).
    """
    sections: list[str] = []

    def _render_group(group_name: str, items: list[Evidence]) -> None:
        filtered, _ = _filter_source_evidence(items)
        if not filtered:
            return
        lines = [f"## {group_name}"]
        for i, ev in enumerate(filtered, 1):
            title = ev.title or "Untitled"
            source = ev.source_name or ev.source_url or ev.id
            date = _evidence_date(ev)
            lines.append(f"\n**[{i}] {title}**")
            lines.append(f"- Source: {source}")
            if date:
                lines.append(f"- Date: {date}")
            if ev.source_url:
                lines.append(f"- URL: {ev.source_url}")
            lines.append(f"- Excerpt: {_excerpt(ev.text, 500)}")
        sections.append("\n".join(lines))

    _render_group("Knowledge Base", knowledge_base_items)
    if web_search_items is not None:
        _render_group("Web Search", web_search_items)
    if not sections:
        return None
    # display="page": the chip is shown in the answer but the sources only open on click
    # (display="side" auto-opens the side panel when attached, which is not wanted).
    return cl.Text(name="📚 Sources", content="\n\n".join(sections), display="page")


def _source_element_payloads(
    knowledge_base_items: list[Evidence],
    web_search_items: list[Evidence] | None = None,
) -> list[dict[str, str]]:
    return [
        {
            "name": element.name,
            "content": element.content,
            "display": element.display,
        }
        for element in _source_elements(knowledge_base_items, web_search_items)
    ]


def _source_action(source_key: str) -> cl.Action:
    payload = {"source_key": source_key}
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    candidates = (
        {"name": _SOURCES_ACTION, "label": "📚 Sources", "payload": payload},
        {"name": _SOURCES_ACTION, "label": "📚 Sources", "value": serialized},
        {"name": _SOURCES_ACTION, "value": serialized, "description": "📚 Sources"},
    )
    last_error: Exception | None = None
    for kwargs in candidates:
        try:
            return cl.Action(**kwargs)
        except Exception as e:  # Chainlit Action fields differ across supported 1.x releases.
            last_error = e
    raise TypeError("could not build Chainlit sources action") from last_error


def _source_actions(
    knowledge_base_items: list[Evidence],
    web_search_items: list[Evidence] | None = None,
) -> list[cl.Action]:
    source_key = f"{_SOURCES_SESSION_PREFIX}{time.time_ns()}"
    if not _store_source_payload(source_key, knowledge_base_items, web_search_items):
        return []
    return [_source_action(source_key)]


def _store_source_payload(
    source_key: str,
    knowledge_base_items: list[Evidence],
    web_search_items: list[Evidence] | None = None,
) -> bool:
    payloads = _source_element_payloads(knowledge_base_items, web_search_items)
    if not payloads:
        return False
    cl.user_session.set(source_key, payloads)
    return True


def _replace_source_actions(
    msg: cl.Message,
    knowledge_base_items: list[Evidence],
    web_search_items: list[Evidence] | None = None,
) -> None:
    actions = list(getattr(msg, "actions", None) or [])
    source_action = next(
        (action for action in actions if getattr(action, "name", None) == _SOURCES_ACTION),
        None,
    )
    existing = [
        action for action in actions
        if getattr(action, "name", None) != _SOURCES_ACTION
    ]
    if source_action is None:
        msg.actions = [*_source_actions(knowledge_base_items, web_search_items), *existing]
        return

    payload = _payload_from_action(source_action)
    source_key = str(payload.get("source_key") or "")
    if not source_key:
        msg.actions = [*_source_actions(knowledge_base_items, web_search_items), *existing]
        return

    if _store_source_payload(source_key, knowledge_base_items, web_search_items):
        msg.actions = [source_action, *existing]
    else:
        msg.actions = existing


def _evidence_date(evidence: Evidence) -> str:
    for key in ("date", "target_date", "created_at", "updated_at", "published_at"):
        value = evidence.metadata.get(key)
        if value:
            return str(value)
    if months := evidence.metadata.get("months"):
        return ",".join(str(month) for month in months)
    return ""


def _excerpt(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)].rstrip() + "..."


def _feedback_payload(
    config: Config,
    *,
    question: str,
    answer: str,
    rating: str,
    feedback_key: str,
) -> dict[str, str]:
    return {
        "trace_path": str(default_trace_path(config.root)),
        "question": question,
        "answer": _excerpt(answer, _FEEDBACK_ANSWER_LIMIT),
        "rating": rating,
        "feedback_key": feedback_key,
    }


def _feedback_action(label: str, payload: dict[str, str]) -> cl.Action:
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    candidates = (
        {"name": _FEEDBACK_ACTION, "label": label, "payload": payload},
        {"name": _FEEDBACK_ACTION, "label": label, "value": serialized},
        {"name": _FEEDBACK_ACTION, "value": serialized, "description": label},
    )
    last_error: Exception | None = None
    for kwargs in candidates:
        try:
            return cl.Action(**kwargs)
        except Exception as e:  # Chainlit Action fields differ across supported 1.x releases.
            last_error = e
    raise TypeError("could not build Chainlit feedback action") from last_error


def _feedback_actions(config: Config, *, question: str, answer: str) -> list[cl.Action]:
    feedback_key = f"{_FEEDBACK_SESSION_PREFIX}{time.time_ns()}"
    return [
        _feedback_action(
            "👍 Helpful",
            _feedback_payload(
                config,
                question=question,
                answer=answer,
                rating="helpful",
                feedback_key=feedback_key,
            ),
        ),
        _feedback_action(
            "👎 Not helpful",
            _feedback_payload(
                config,
                question=question,
                answer=answer,
                rating="unhelpful",
                feedback_key=feedback_key,
            ),
        ),
    ]


async def _attach_feedback_actions(
    config: Config,
    msg: cl.Message,
    *,
    question: str,
    answer: str,
) -> None:
    if not answer:
        return
    existing = [
        action for action in (getattr(msg, "actions", None) or [])
        if getattr(action, "name", None) != _FEEDBACK_ACTION
    ]
    msg.actions = [*existing, *_feedback_actions(config, question=question, answer=answer)]
    await msg.update()


def _feedback_status_text(rating: str) -> str:
    marker = "👍" if rating == "helpful" else "👎"
    return f"Recorded: {marker}"


async def _update_feedback_status(feedback_key: str, rating: str) -> None:
    content = _feedback_status_text(rating)
    stored = cl.user_session.get(feedback_key) if feedback_key else None
    if stored is not None and hasattr(stored, "content") and hasattr(stored, "update"):
        stored.content = content
        await stored.update()
        return

    msg = cl.Message(content=content)
    await msg.send()
    if feedback_key:
        cl.user_session.set(feedback_key, msg)


def _payload_from_action(action: cl.Action) -> dict[str, Any]:
    payload = getattr(action, "payload", None)
    if isinstance(payload, dict):
        return payload
    value = getattr(action, "value", None)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


@cl.action_callback(_SOURCES_ACTION)
async def on_sources(action: cl.Action) -> None:
    """Show answer sources only after the user asks for them."""
    payload = _payload_from_action(action)
    source_key = str(payload.get("source_key") or "")
    stored = cl.user_session.get(source_key) if source_key else None
    if not isinstance(stored, list) or not stored:
        await cl.Message(content="No sources available.").send()
        return

    elements = [
        cl.Text(**item)
        for item in stored
        if isinstance(item, dict)
    ]
    if not elements:
        await cl.Message(content="No sources available.").send()
        return
    await cl.Message(content="Sources", elements=elements).send()


def _tool_arguments(tool_call: ToolCall) -> dict[str, Any]:
    try:
        parsed = json.loads(tool_call.function_arguments or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _tool_label(tool_call: ToolCall) -> str:
    arguments = _tool_arguments(tool_call)
    if not arguments:
        return f"{tool_call.function_name}()"
    rendered = ", ".join(f"{key}={value}" for key, value in list(arguments.items())[:4])
    return f"{tool_call.function_name}({rendered})"


def _tool_result_summary(tool_call: ToolCall, fresh: list[Evidence]) -> str:
    label = _tool_label(tool_call)
    if tool_call.function_name == "fetch_cafeteria_menu":
        menu_lines = [
            line for item in fresh for line in item.text.splitlines()
            if line.strip() and not line.startswith("오늘:")
        ]
        return f"{label} → {len(menu_lines)} cafeteria menus"
    result_label = "result" if len(fresh) == 1 else "results"
    return f"{label} → {len(fresh)} {result_label}"


@cl.action_callback(_FEEDBACK_ACTION)
async def on_feedback(action: cl.Action) -> None:
    """Persist explicit user feedback for an answer message."""
    payload = _payload_from_action(action)
    trace_path = payload.get("trace_path")
    question = str(payload.get("question") or "")
    answer = str(payload.get("answer") or "")
    rating = str(payload.get("rating") or "")
    feedback_key = str(payload.get("feedback_key") or "")
    if not trace_path or rating not in {"helpful", "unhelpful"}:
        await cl.Message(content="Could not record feedback.").send()
        return

    append_feedback(
        trace_path,
        question=question,
        answer=answer,
        rating=rating,  # type: ignore[arg-type]
    )
    # Record silently: do not spawn a new chat message (keeps the feedback buttons
    # fixed on the answer). Show an ephemeral toast when the Chainlit build supports it.
    marker = "👍" if rating == "helpful" else "👎"
    try:
        await cl.context.emitter.send_toast(f"피드백이 기록되었습니다 {marker}", type="success")
    except Exception:
        pass


async def _stream_to_message(
    llm: Any,
    messages: list[Message],
    msg: cl.Message,
    *,
    model: str,
    temperature: float,
    max_tokens: int,
    tools: list[dict[str, object]] | None = None,
) -> StreamOutcome:
    if not hasattr(llm, "stream_chat"):
        result = await cl.make_async(llm.chat)(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
        )
        msg.content = result.content
        await msg.update()
        return StreamOutcome(content=result.content, marker_detected=False)

    tokens: list[str] = []
    for token in llm.stream_chat(
        messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
    ):
        tokens.append(token)
        content = "".join(tokens)
        if has_stream_tool_call_marker(content):
            msg.content = ""
            await msg.update()
            return StreamOutcome(content=content, marker_detected=True)
        await msg.stream_token(token)
    await msg.update()
    return StreamOutcome(content="".join(tokens), marker_detected=False)


def _append_ui_trace(
    config: Config,
    *,
    started: float,
    question: str,
    answer: str,
    evidence: list[Evidence],
    tools_called: list[str],
    tool_args: list[dict[str, Any]],
    mode: str,
    usage: dict[str, Any] | None = None,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    append_chat_trace(
        default_trace_path(config.root),
        source="ui",
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


@cl.on_chat_start
async def on_chat_start() -> None:
    """Initialize session state on chat start."""
    workspace: str | Path | None = os.environ.get("SUTRA_WORKSPACE")
    if not workspace or (isinstance(workspace, str) and not workspace.strip()):
        default_workspace = _default_workspace_path()
        if default_workspace.exists():
            workspace = default_workspace.resolve()
        else:
            workspace = None
            await cl.Message(
                content=(
                    "**오류**: 워크스페이스 설정을 찾을 수 없습니다. "
                    "SUTRA_WORKSPACE를 설정하거나 examples/cnu-campus/sutra.toml 파일을 확인하세요."
                ),
            ).send()
    echo = os.environ.get("SUTRA_ECHO") == "1"
    cl.user_session.set("workspace", workspace)
    cl.user_session.set("echo", echo)
    cl.user_session.set("client", EchoClient() if echo else None)


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Handle an incoming chat message."""
    started = time.perf_counter()
    client = cl.user_session.get("client")
    workspace = cl.user_session.get("workspace")
    question = message.content
    tools_called: list[str] = []
    tool_args: list[dict[str, Any]] = []

    try:
        config = workspace if isinstance(workspace, Config) else load_config(workspace)
    except SutraError as e:
        await cl.Message(content=f"**오류**: {e}").send()
        return

    routed_domain, forced_tool, label = route_question(question, config)
    classifier_fallback = label is None
    trace_extra = {
        "routed_domain": routed_domain,
        "forced_tool": forced_tool,
        "classifier_fallback": classifier_fallback,
    }

    try:
        async with cl.Step(name=RETRIEVAL_STEP_NAME, type="retrieval") as step:
            documents = await cl.make_async(load_documents)(config)
            evidence = await cl.make_async(retrieve)(question, documents, config)
            shown_items, hidden_count = _filter_source_evidence(evidence.items)
            step.output = _source_filter_summary(evidence.items, len(shown_items), hidden_count)
    except Exception as e:
        _append_ui_trace(
            config,
            started=started,
            question=question,
            answer="",
            evidence=[],
            tools_called=[],
            tool_args=[],
            mode="retrieval_error",
            error=str(e),
            extra=trace_extra,
        )
        await cl.Message(content="**Error**: Search failed.").send()
        return

    rag_items = list(evidence.items)
    fresh_items: list[Evidence] = []
    if not rag_items and forced_tool is None:
        answer = "제공된 자료에서 확인할 수 있는 근거를 찾지 못했습니다."
        _append_ui_trace(
            config,
            started=started,
            question=question,
            answer=answer,
            evidence=[],
            tools_called=[],
            tool_args=[],
            mode="router_insufficient_evidence",
            extra=trace_extra,
        )
        await cl.Message(
            content=answer,
            actions=_feedback_actions(config, question=question, answer=answer),
        ).send()
        return

    llm = client or LlamaClient(
        config.runtime.base_url,
        timeout_seconds=config.runtime.timeout_seconds,
    )
    result: LlamaResult | None = None
    final_answer = ""
    final_msg: cl.Message | None = None
    evidence_for_trace = list(rag_items)
    mode = "router_llm_stream"
    try:
        if forced_tool is not None:
            tools = get_tool_definitions()
            result = await cl.make_async(llm.chat)(
                _render_router_tool_request_messages(question, config),
                model=config.runtime.model,
                temperature=config.runtime.temperature,
                max_tokens=min(config.runtime.max_tokens, 256),
                tools=tools or None,
                tool_choice=_forced_tool_choice(forced_tool),
            )
            async with cl.Step(name=LIVE_LOOKUP_STEP_NAME, type="tool") as step:
                tool_labels = [_tool_label(tc) for tc in result.tool_calls]
                step.input = "; ".join(tool_labels) if tool_labels else f"{forced_tool}()"
                tool_summaries: list[str] = []
                for tool_call in result.tool_calls:
                    tools_called.append(tool_call.function_name)
                    tool_args.append(_tool_arguments(tool_call))
                    if tool_call.function_name != forced_tool:
                        logger.warning(
                            "Router forced %s but model returned %s; ignoring tool evidence",
                            forced_tool,
                            tool_call.function_name,
                        )
                        continue
                    fresh = await cl.make_async(dispatch)(
                        tool_call.function_name,
                        tool_call.function_arguments,
                    )
                    fresh_items.extend(fresh)
                    tool_summaries.append(_tool_result_summary(tool_call, fresh))
                step.output = "; ".join(tool_summaries) if tool_summaries else f"{forced_tool}() → 0 results"

        if forced_tool is not None and not fresh_items and not rag_items:
            final_answer = (
                "실시간 조회에 실패했고 저장된 자료에서도 관련 정보를 찾지 못했습니다. "
                "충남대학교 공식 홈페이지를 확인해 주세요."
            )
            final_msg = cl.Message(content=final_answer)
            await final_msg.send()
            mode = "router_tool_no_result"
        else:
            use_fresh_only = forced_tool is not None and bool(fresh_items)
            evidence_for_prompt = list(fresh_items) if use_fresh_only else list(rag_items)
            evidence_for_trace = evidence_for_prompt
            prompt = await cl.make_async(render_prompt)(
                question,
                EvidencePack(question=question, items=evidence_for_prompt),
                config,
            )
            final_msg = cl.Message(content="")
            await final_msg.send()
            if fresh_items:
                mode = "router_tool_stream"
            elif forced_tool is not None:
                mode = "router_tool_no_result"
            else:
                mode = "router_llm_stream"

            outcome = await _stream_to_message(
                llm,
                prompt.messages,
                final_msg,
                model=config.runtime.model,
                temperature=config.runtime.temperature,
                max_tokens=config.runtime.max_tokens,
            )
            final_answer = outcome.content
            if outcome.marker_detected or not final_answer:
                fallback_result = await cl.make_async(llm.chat)(
                    prompt.messages,
                    model=config.runtime.model,
                    temperature=config.runtime.temperature,
                    max_tokens=config.runtime.max_tokens,
                )
                result = fallback_result
                final_answer = fallback_result.content
                final_msg.content = final_answer
                await final_msg.update()
            if forced_tool is not None and not fresh_items:
                final_answer += "\n\n(실시간 정보를 가져오지 못해 저장된 자료를 기준으로 답변했습니다.)"
                final_msg.content = final_answer
                await final_msg.update()

            if result is None:
                result = LlamaResult(content=final_answer, model=config.runtime.model)

        if forced_tool is not None and fresh_items:
            evidence_for_trace = list(fresh_items)
        elif forced_tool is not None:
            evidence_for_trace = rag_items

        if final_msg is None:
            final_msg = cl.Message(content=final_answer)
            await final_msg.send()

        if result is None:
            result = LlamaResult(content=final_answer, model=config.runtime.model)

        if fresh_items and final_msg.content != final_answer:
            final_msg.content = final_answer
            await final_msg.update()

        if final_answer:
            sources_element = _sources_element(
                [] if forced_tool is not None and fresh_items else rag_items,
                fresh_items if forced_tool is not None and fresh_items else None,
            )
            if sources_element is not None:
                # A side element only renders a clickable chip when its name is referenced
                # in the message content. Append a footer reference so the user gets a single
                # "📚 Sources" chip that opens the side panel on click (not auto-expanded).
                final_msg.content = f"{final_answer}\n\n{sources_element.name}"
                final_msg.elements = [sources_element]
                await final_msg.update()

        if final_answer == "" and result.content:
            final_answer = result.content
            final_msg.content = final_answer
            await final_msg.update()

        if forced_tool is not None and fresh_items:
            mode = "router_tool_stream"
        elif forced_tool is not None:
            mode = "router_tool_no_result"
        else:
            mode = "router_llm_stream"

        _append_ui_trace(
            config,
            started=started,
            question=question,
            answer=final_answer,
            evidence=evidence_for_trace,
            tools_called=tools_called,
            tool_args=tool_args,
            mode=mode,
            usage=result.usage if result is not None else None,
            error=None,
            extra=trace_extra,
        )
        await _attach_feedback_actions(config, final_msg, question=question, answer=final_answer)
    except Exception as e:
        _append_ui_trace(
            config,
            started=started,
            question=question,
            answer=final_answer,
            evidence=evidence_for_trace,
            tools_called=tools_called,
            tool_args=tool_args,
            mode="generation_error",
            usage=result.usage if result is not None else None,
            error=str(e),
            extra=trace_extra,
        )
        await cl.Message(content="**Error**: Response generation failed.").send()
