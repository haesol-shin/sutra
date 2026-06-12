from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sutra.config import Config, WorkspacePeriod
from sutra.models import EvidencePack, Message, PromptBundle
from sutra.retrieval import render_evidence


def get_current_time_str(timezone_name: str) -> str:
    """Get current time as a formatted string for the given timezone."""
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")
    
    now = datetime.now(tz)
    
    weekdays_eng = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekdays_kor = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    
    weekday_idx = now.weekday()
    weekday_eng = weekdays_eng[weekday_idx]
    weekday_kor = weekdays_kor[weekday_idx]
    
    return f"{now.strftime('%Y-%m-%d')} {weekday_eng} ({weekday_kor})"


def get_current_date(timezone_name: str) -> date:
    """Return today's date in the workspace timezone."""
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")
    return datetime.now(tz).date()


def build_relative_date_anchors(today: date) -> str:
    """Return compact Korean relative-date anchors with explicit ISO dates."""
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    anchors = [
        ("오늘", today),
        ("어제", today - timedelta(days=1)),
        ("내일", today + timedelta(days=1)),
        ("모레", today + timedelta(days=2)),
    ]
    return " | ".join(f"{label}: {value:%Y-%m-%d} ({weekdays[value.weekday()]})" for label, value in anchors)


def build_temporal_context(today: date, periods: "list[WorkspacePeriod] | None" = None) -> str:
    """Resolve this/next week date ranges and the current named period (if any).

    Week ranges are pure date math (generic). The current-period anchor is only
    emitted when the workspace defines `periods` in its config — no project- or
    domain-specific calendar is baked into the engine. Pre-computing these removes
    the model's burden of mapping today's date to period semantics, which it does
    unreliably (e.g. it labeled June as 제2학기 instead of 제1학기)."""
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    next_monday = monday + timedelta(days=7)
    next_sunday = monday + timedelta(days=13)
    this_week = f"{monday:%Y-%m-%d}(월) ~ {sunday:%Y-%m-%d}(일), 평일 {monday:%m-%d}~{monday + timedelta(days=4):%m-%d}"
    next_week = f"{next_monday:%Y-%m-%d}(월) ~ {next_sunday:%Y-%m-%d}(일), 평일 {next_monday:%m-%d}~{next_monday + timedelta(days=4):%m-%d}, 주말 {next_monday + timedelta(days=5):%m-%d}~{next_sunday:%m-%d}"
    lines: list[str] = []
    label = next((p.label for p in (periods or []) if p.start <= today <= p.end), None)
    if label:
        lines.append(f"현재 기간: {label}")
    lines.append(f"이번 주: {this_week}")
    lines.append(f"다음 주: {next_week}")
    return "\n".join(lines)


def build_forced_tool_temporal_context(today: date, periods: "list[WorkspacePeriod] | None" = None) -> str:
    """Shared temporal context for answer prompts and forced tool requests."""
    return f"{build_relative_date_anchors(today)}\n{build_temporal_context(today, periods)}"


def render_prompt(question: str, evidence: EvidencePack, config: Config) -> PromptBundle:
    """Build a PromptBundle with system prompt, question, and evidence context."""
    system = config.prompts.system.read_text(encoding="utf-8").strip()
    context = render_evidence(evidence)
    
    current_time = get_current_time_str(config.workspace.timezone)
    temporal_context = build_forced_tool_temporal_context(
        get_current_date(config.workspace.timezone), config.workspace.periods
    )
    
    user = (
        f"Workspace: {config.workspace.name}\n"
        f"Timezone: {config.workspace.timezone}\n"
        f"Current Time: {current_time}\n"
        f"{temporal_context}\n\n"
        f"Question:\n{question}\n\n"
        f"Evidence:\n{context}"
    )
    return PromptBundle(
        messages=[
            Message(role="system", content=system),
            Message(role="user", content=user),
        ],
        context=context,
    )
