from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sutra.config import Config
from sutra.models import EvidencePack, Message, PromptBundle
from sutra.retrieval import render_evidence
from sutra.tools import get_tool_definitions


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
    tools = get_tool_definitions()
    if tools:
        tool_lines = []
        for t in tools:
            name = t['function']['name']
            desc = t['function']['description']
            tool_lines.append(f"- {name}: {desc}")
        system += "\n\nYou have access to the following tools. Use them when appropriate:\n" + "\n".join(tool_lines)
    context = render_evidence(evidence)
    
    current_time = get_current_time_str(config.workspace.timezone)
    
    user = (
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

