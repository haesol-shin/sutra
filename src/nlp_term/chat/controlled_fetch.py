from __future__ import annotations

from collections.abc import Iterable

from nlp_term.collect.source_inventory import SourceSpec
from nlp_term.schemas import Domain


CONTROLLED_FETCH_SUPPORTED_PARSERS = frozenset({"html", "board_detail", "pdf", "hwp", "hwpx", "calendar", "shuttle"})


def fetchable_specs(
    specs: Iterable[SourceSpec],
    *,
    route_domain: Domain,
) -> list[SourceSpec]:
    return [
        spec
        for spec in specs
        if spec.active and spec.domain == route_domain and spec.parser_type in CONTROLLED_FETCH_SUPPORTED_PARSERS
    ]
