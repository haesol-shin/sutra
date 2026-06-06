from __future__ import annotations

from pathlib import Path

from nlp_term.chat.router import RoutedQuestion
from nlp_term.llm.env_probe import executable_path
from nlp_term.llm.llama_compare import DEFAULT_MODEL_PATH, build_retrieval_prompt, run_llama
from nlp_term.llm.prompt_eval import build_context, context_text
from nlp_term.retrieve.knowledge import load_knowledge


def llama_backend_available(model_path: Path = DEFAULT_MODEL_PATH) -> bool:
    return model_path.exists() and executable_path("llama-cli") is not None


def generate_llama_answer(
    route: RoutedQuestion,
    *,
    knowledge_path: Path | None,
    model_path: Path = DEFAULT_MODEL_PATH,
    context_size: int = 2048,
    max_new_tokens: int = 128,
    timeout_seconds: int = 240,
) -> str:
    llama_path = executable_path("llama-cli")
    if llama_path is None:
        raise RuntimeError("llama-cli was not found")
    if not model_path.exists():
        raise FileNotFoundError(model_path)

    docs = load_knowledge(knowledge_path)
    selected_docs = build_context(route.user, docs, top_k=3, max_doc_chars=700)
    context = context_text(selected_docs).replace("\ufffd", " ")
    prompt = build_retrieval_prompt(route.user, context)
    result = run_llama(
        llama_path,
        model_path,
        prompt,
        context_size=context_size,
        max_new_tokens=max_new_tokens,
        timeout_seconds=timeout_seconds,
    )
    if result["returncode"] != 0:
        raise RuntimeError(result["stderr"] or "llama.cpp generation failed")
    answer = str(result["answer"]).strip()
    if not answer:
        raise RuntimeError("llama.cpp returned an empty answer")
    return answer
