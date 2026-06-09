from __future__ import annotations

from sutra.config import Config
from sutra.errors import ConfigError
from sutra.models import EvidencePack, Message, PromptBundle
from sutra.retrieval import render_evidence


def render_prompt(question: str, evidence: EvidencePack, config: Config) -> PromptBundle:
    system = config.prompts.system.read_text(encoding="utf-8").strip()
    answer_template = _read_answer_template(config)
    context = render_evidence(evidence)
    user = (
        f"{answer_template}\n\n"
        f"Workspace: {config.workspace.name}\n"
        f"Timezone: {config.workspace.timezone}\n\n"
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
