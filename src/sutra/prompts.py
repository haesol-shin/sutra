from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sutra.config import Config
from sutra.errors import ConfigError
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


def render_prompt(question: str, evidence: EvidencePack, config: Config) -> PromptBundle:
    """Build a PromptBundle with system prompt, question, and evidence context."""
    system = config.prompts.system.read_text(encoding="utf-8").strip()
    answer_template = _read_answer_template(config)
    context = render_evidence(evidence)
    
    current_time = get_current_time_str(config.workspace.timezone)
    
    user = (
        f"{answer_template}\n\n"
        f"Workspace: {config.workspace.name}\n"
        f"Timezone: {config.workspace.timezone}\n"
        f"Current Time: {current_time}\n\n"
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


def _read_answer_template(config: Config) -> str:
    if config.prompts.answer is None:
        return "Answer the user using only the evidence context. If evidence is insufficient, say what is missing."
    if not config.prompts.answer.exists():
        raise ConfigError(f"configured answer prompt not found: {config.prompts.answer}")
    return config.prompts.answer.read_text(encoding="utf-8").strip()

