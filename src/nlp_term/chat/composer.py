from __future__ import annotations

from nlp_term.chat.router import RoutedQuestion
from nlp_term.chat.templates import fallback_answer


def compose_answer(route: RoutedQuestion) -> str:
    return fallback_answer(route)
