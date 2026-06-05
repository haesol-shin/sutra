from __future__ import annotations

from dataclasses import dataclass

from nlp_term.classify.predict import predict_label


DOMAINS = {
    0: "graduation",
    1: "notices",
    2: "academic_calendar",
    3: "dining",
    4: "shuttle",
}


@dataclass(frozen=True)
class RoutedQuestion:
    user: str
    label: int
    domain: str


def route_question(user: str) -> RoutedQuestion:
    label = predict_label(user)
    return RoutedQuestion(user=user, label=label, domain=DOMAINS[label])
