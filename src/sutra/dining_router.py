from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from sutra.config import Config
from sutra.menu_resolver import resolve_cafeteria, resolve_menu_dates
from sutra.models import Evidence
from sutra.tools import CAFETERIA_MENU_CHOICES

_REFUSAL_TEXT = "요청하신 날짜를 정확히 해석하지 못했습니다. 날짜를 YYYY-MM-DD 또는 오늘/내일/이번주처럼 다시 알려주세요."
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class DiningOutcome:
    evidence: list[Evidence]
    called_tools: list[str]
    tool_args: list[dict[str, Any]]
    use_kb_fallback: bool
    refused: bool
    refusal_text: str | None


def run_forced_cafeteria_call(
    *,
    question: str,
    config: Config,
    tool_calls: Iterable[Any],
    call_model: Callable[[], Any],
    dispatch_fn: Callable[[str, dict[str, Any]], list[Evidence]],
) -> DiningOutcome:
    """Apply the shared forced-cafeteria routing policy."""
    called_tools: list[str] = []
    tool_args: list[dict[str, Any]] = []
    fetch_call = _first_fetch_call(tool_calls, called_tools, tool_args)
    if fetch_call is None:
        return DiningOutcome([], called_tools, tool_args, False, False, None)

    args = _tool_arguments_dict(fetch_call)
    cafeteria = _choose_cafeteria(question, args)
    if cafeteria == "제1학생회관":
        called_tools.append("fetch_cafeteria_menu:food_court_skip")
        tool_args.append({**args, "_sutra_skip": "food_court"})
        return DiningOutcome([], called_tools, tool_args, True, False, None)

    resolved_dates = resolve_menu_dates(question, config)
    model_dates = _model_dates(args)
    if resolved_dates is None and model_dates:
        retry_result = call_model()
        retry_called_tools: list[str] = []
        retry_tool_args: list[dict[str, Any]] = []
        retry_fetch_call = _first_fetch_call(
            getattr(retry_result, "tool_calls", []) or [], retry_called_tools, retry_tool_args
        )
        if retry_fetch_call is None:
            called_tools.extend(retry_called_tools)
            tool_args.extend(retry_tool_args)
            return DiningOutcome([], called_tools, tool_args, False, False, None)
        args = _tool_arguments_dict(retry_fetch_call)
        cafeteria = _choose_cafeteria(question, args)
        if cafeteria == "제1학생회관":
            called_tools.append("fetch_cafeteria_menu:food_court_skip")
            tool_args.append({**args, "_sutra_skip": "food_court"})
            return DiningOutcome([], called_tools, tool_args, True, False, None)
        resolved_dates = resolve_menu_dates(question, config)
        model_dates = _model_dates(args)
        if resolved_dates is None and model_dates:
            return DiningOutcome([], called_tools, tool_args, False, True, _REFUSAL_TEXT)

    dispatch_args: dict[str, Any] = {"cafeteria": cafeteria}
    if resolved_dates is not None:
        dispatch_args["dates"] = resolved_dates
    called_tools.append("fetch_cafeteria_menu")
    tool_args.append(dict(dispatch_args))
    fresh = dispatch_fn("fetch_cafeteria_menu", dispatch_args)
    return DiningOutcome(list(fresh), called_tools, tool_args, False, False, None)


def _first_fetch_call(
    tool_calls: Iterable[Any], called_tools: list[str], tool_args: list[dict[str, Any]]
) -> Any | None:
    for tool_call in tool_calls:
        function_name = getattr(tool_call, "function_name", "")
        if function_name == "fetch_cafeteria_menu":
            return tool_call
        called_tools.append(function_name)
        tool_args.append(_tool_arguments_dict(tool_call))
    return None


def _tool_arguments_dict(tool_call: Any) -> dict[str, Any]:
    raw_args = getattr(tool_call, "function_arguments", None)
    if isinstance(raw_args, dict):
        return raw_args
    if not raw_args:
        return {}
    try:
        parsed = json.loads(raw_args)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _map_cafeteria(value: Any) -> str | None:
    if value == "제1학생회관":
        return "제1학생회관"
    if value in CAFETERIA_MENU_CHOICES:
        return str(value)
    return None

def _choose_cafeteria(question: str, args: dict[str, Any]) -> str | None:
    """Question-derived cafeteria is authoritative (9B enum picking is unreliable);
    fall back to the model-supplied enum only when the question names no cafeteria."""
    from_question = resolve_cafeteria(question)
    if from_question is not None:
        return from_question
    return _map_cafeteria(args.get("cafeteria"))


def _model_dates(args: dict[str, Any]) -> list[str]:
    raw_dates = args.get("dates")
    if isinstance(raw_dates, str):
        dates = [raw_dates]
    elif isinstance(raw_dates, (list, tuple)):
        dates = [item for item in raw_dates if isinstance(item, str)]
    else:
        legacy_date = args.get("date")
        dates = [legacy_date] if isinstance(legacy_date, str) else []
    return [item for item in dates if _ISO_DATE_RE.match(item)]
