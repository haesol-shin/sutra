from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sutra.config import Config
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


# CNU 2026 academic-year period boundaries. Used to inject a resolved
# current-period anchor so the model does not misread relative expressions like
# "이번 학기" (observed: model labels June as 제2학기 instead of 제1학기).
_ACADEMIC_PERIODS: list[tuple[str, date, date]] = [
    ("2026학년도 제1학기", date(2026, 3, 3), date(2026, 6, 21)),
    ("하기방학 (하기 계절학기 2026-06-22~07-10)", date(2026, 6, 22), date(2026, 8, 31)),
    ("2026학년도 제2학기", date(2026, 9, 1), date(2026, 12, 20)),
    ("동기방학 (동기 계절학기 2026-12-21~2027-01-12)", date(2026, 12, 21), date(2027, 2, 28)),
]


def get_current_date(timezone_name: str) -> date:
    """Return today's date in the workspace timezone."""
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")
    return datetime.now(tz).date()


def build_academic_context(today: date) -> str:
    """Resolve the current academic period + this/next week date ranges.

    Pre-computing these removes the model's burden of mapping the current date to
    academic-period semantics, which it does unreliably (esp. '이번 학기')."""
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    next_monday = monday + timedelta(days=7)
    next_sunday = monday + timedelta(days=13)
    this_week = f"{monday:%Y-%m-%d}(월) ~ {sunday:%Y-%m-%d}(일), 평일 {monday:%m-%d}~{monday + timedelta(days=4):%m-%d}"
    next_week = f"{next_monday:%Y-%m-%d}(월) ~ {next_sunday:%Y-%m-%d}(일), 평일 {next_monday:%m-%d}~{next_monday + timedelta(days=4):%m-%d}, 주말 {next_monday + timedelta(days=5):%m-%d}~{next_sunday:%m-%d}"
    lines: list[str] = []
    period = next((name for name, start, end in _ACADEMIC_PERIODS if start <= today <= end), None)
    if period:
        lines.append(f"현재 학업 기간: {period}")
    lines.append(f"이번 주: {this_week}")
    lines.append(f"다음 주: {next_week}")
    return "\n".join(lines)


def render_prompt(question: str, evidence: EvidencePack, config: Config) -> PromptBundle:
    """Build a PromptBundle with system prompt, question, and evidence context."""
    system = config.prompts.system.read_text(encoding="utf-8").strip()
    context = render_evidence(evidence)
    
    current_time = get_current_time_str(config.workspace.timezone)
    academic_context = build_academic_context(get_current_date(config.workspace.timezone))
    
    user = (
        f"Workspace: {config.workspace.name}\n"
        f"Timezone: {config.workspace.timezone}\n"
        f"Current Time: {current_time}\n"
        f"{academic_context}\n\n"
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
