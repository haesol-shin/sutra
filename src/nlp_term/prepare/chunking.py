from __future__ import annotations

from dataclasses import dataclass
import re


DATE_ROW_RE = re.compile(r"(?:20\d{2}[-.]\d{1,2}[-.]\d{1,2}|\d{2}\.\d{2})")
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
DINING_HEADER_RE = re.compile(
    r"20\d{2}-\d{2}-\d{2}.*(?:학생회관|생활관|푸드코트).*(?:조식|중식|석식|점심|저녁|아침)"
)
NOTICE_FIELD_RE = re.compile(r"^(제목|작성일|게시일|본문)\s*[:：]")
GRAD_REQUIREMENT_RE = re.compile(r"(?:학번|졸업|전공|교양|학점|프로젝트|이수)")


@dataclass(frozen=True)
class SourceChunk:
    text: str
    strategy: str
    index: int
    boundary_type: str
    chunk_confidence: str
    char_start: int | None = None
    char_end: int | None = None


def split_source_text(
    text: str,
    *,
    label: int,
    max_chunk_chars: int = 300,
    max_chunks: int = 9,
) -> list[SourceChunk]:
    guarded = _atomic_guard_chunks(text, label=label, max_chunk_chars=max_chunk_chars, max_chunks=max_chunks)
    if guarded:
        return guarded
    recursive = _recursive_prose_chunks(text, max_chunk_chars=max_chunk_chars, max_chunks=max_chunks)
    if recursive:
        return recursive
    return _fallback_window_chunks(text, max_chunk_chars=max_chunk_chars, max_chunks=max_chunks)


def _atomic_guard_chunks(text: str, *, label: int, max_chunk_chars: int, max_chunks: int) -> list[SourceChunk]:
    lines = _clean_lines(text)
    if label == 0:
        units = _graduation_guard_units(lines)
    elif label == 1:
        units = _notice_guard_units(lines)
    elif label == 2:
        units = [(line, "calendar_row") for line in lines if DATE_ROW_RE.search(line)]
    elif label == 3:
        units = _dining_guard_units(lines)
    elif label == 4:
        units = _shuttle_guard_units(lines)
    else:
        units = []
    return _materialize_units(
        units,
        strategy="atomic_guard",
        confidence="high",
        max_chunk_chars=max_chunk_chars,
        max_chunks=max_chunks,
    )


def _clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]


def _graduation_guard_units(lines: list[str]) -> list[tuple[str, str]]:
    units: list[tuple[str, str]] = []
    current_heading = ""
    for line in lines:
        if len(line) <= 40 and any(term in line for term in ("졸업", "교육과정", "요건")):
            current_heading = line
            continue
        if current_heading and GRAD_REQUIREMENT_RE.search(line):
            units.append((f"{current_heading} {line}".strip(), "graduation_requirement"))
    return units


def _notice_guard_units(lines: list[str]) -> list[tuple[str, str]]:
    fields = [line for line in lines if NOTICE_FIELD_RE.search(line)]
    if len(fields) >= 2:
        return [(" ".join(fields), "notice_detail")]
    return []


def _dining_guard_units(lines: list[str]) -> list[tuple[str, str]]:
    units: list[tuple[str, str]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if DINING_HEADER_RE.search(line):
            menu = lines[index + 1] if index + 1 < len(lines) else ""
            units.append((f"{line} {menu}".strip(), "dining_menu_row"))
            index += 2
            continue
        index += 1
    return units


def _shuttle_guard_units(lines: list[str]) -> list[tuple[str, str]]:
    heading = next((line for line in lines if "셔틀" in line or "버스" in line), "")
    units: list[tuple[str, str]] = []
    for line in lines:
        if TIME_RE.search(line):
            units.append((f"{heading} {line}".strip(), "shuttle_time_row"))
    return units


def _recursive_prose_chunks(text: str, *, max_chunk_chars: int, max_chunks: int) -> list[SourceChunk]:
    normalized = " ".join(text.split())
    if not normalized or _looks_unstructured(normalized):
        return []
    parts = [part.strip() for part in re.split(r"(?<=[다요]\.)\s+", normalized) if part.strip()]
    if not parts:
        return []
    units = [(part, "prose_sentence") for part in _merge_parts(parts, max_chunk_chars=max_chunk_chars)]
    return _materialize_units(
        units,
        strategy="recursive_prose",
        confidence="medium",
        max_chunk_chars=max_chunk_chars,
        max_chunks=max_chunks,
    )


def _looks_unstructured(text: str) -> bool:
    return bool(text) and " " not in text and "\n" not in text and len(text) > 80


def _merge_parts(parts: list[str], *, max_chunk_chars: int) -> list[str]:
    merged: list[str] = []
    current = ""
    for part in parts:
        candidate = f"{current} {part}".strip()
        if current and len(candidate) > max_chunk_chars:
            merged.append(current)
            current = part
        else:
            current = candidate
    if current:
        merged.append(current)
    return merged


def _materialize_units(
    units: list[tuple[str, str]],
    *,
    strategy: str,
    confidence: str,
    max_chunk_chars: int,
    max_chunks: int,
) -> list[SourceChunk]:
    chunks: list[SourceChunk] = []
    for text, boundary_type in units:
        normalized = " ".join(text.split())
        if not normalized:
            continue
        if len(normalized) > max_chunk_chars:
            chunks.extend(
                _fallback_window_chunks(
                    normalized,
                    max_chunk_chars=max_chunk_chars,
                    max_chunks=max_chunks - len(chunks),
                    boundary_type=boundary_type,
                )
            )
        else:
            chunks.append(
                SourceChunk(
                    text=normalized,
                    strategy=strategy,
                    index=len(chunks) + 1,
                    boundary_type=boundary_type,
                    chunk_confidence=confidence,
                )
            )
        if len(chunks) >= max_chunks:
            break
    return chunks[:max_chunks]


def _fallback_window_chunks(
    text: str,
    *,
    max_chunk_chars: int,
    max_chunks: int,
    boundary_type: str = "fallback_window",
) -> list[SourceChunk]:
    normalized = " ".join(text.split())
    if not normalized or max_chunks <= 0:
        return []
    chunks: list[SourceChunk] = []
    step = max(max_chunk_chars // 2, 80)
    for start in range(0, len(normalized), step):
        body = normalized[start : start + max_chunk_chars].strip()
        if not body:
            continue
        chunks.append(
            SourceChunk(
                text=body,
                strategy="fallback_window",
                index=len(chunks) + 1,
                boundary_type=boundary_type,
                chunk_confidence="low",
                char_start=start,
                char_end=start + len(body),
            )
        )
        if len(chunks) >= max_chunks:
            break
    return chunks
