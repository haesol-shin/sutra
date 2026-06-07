from __future__ import annotations

from nlp_term.chat.answer_validation import validate_task2_answer


def test_answer_validator_accepts_short_but_natural_grounded_answer() -> None:
    result = validate_task2_answer("확인된 학사일정 기준으로 수강신청 기간을 확인하면 됩니다.")

    assert result.passed is True
    assert result.failures == []
    assert result.answer_chars == len("확인된 학사일정 기준으로 수강신청 기간을 확인하면 됩니다.")


def test_answer_validator_does_not_use_arbitrary_too_short_failure() -> None:
    result = validate_task2_answer("네, 가능합니다.")

    assert result.passed is True
    assert "too_short" not in result.failures
    assert "answer_too_short" not in result.failures


def test_answer_validator_rejects_internal_ids_and_raw_template_text() -> None:
    result = validate_task2_answer("{'answer': 'chunk_12와 source 1을 참고하세요'}")

    assert result.passed is False
    assert "raw_json_or_template_text" in result.failures
    assert "internal_id_exposed" in result.failures


def test_answer_validator_rejects_must_not_claim_exact_matches() -> None:
    result = validate_task2_answer(
        "확인되지 않은 최신 정보입니다.",
        must_not_claim=["확인되지 않은 최신 정보"],
    )

    assert result.passed is False
    assert result.must_not_claim_violations == ["확인되지 않은 최신 정보"]
    assert "must_not_claim_violation" in result.failures


def test_answer_validator_rejects_empty_and_non_korean_text() -> None:
    empty = validate_task2_answer("   ")
    english = validate_task2_answer("Check the official page.")

    assert empty.passed is False
    assert "empty_answer" in empty.failures
    assert english.passed is False
    assert "no_hangul_text" in english.failures


def test_answer_validator_flags_unsupported_url_number_institution_and_menu_claims() -> None:
    result = validate_task2_answer(
        "생화학과 졸업요건은 학생지원센터에서 확인하고, "
        "'학사정보 > 졸업요건' 메뉴의 https://made-up.cnu.ac.kr/grad 를 보세요. "
        "전공은 130점 이상입니다.",
        evidence_texts=[
            "생화학과 졸업요건은 전공과 교양 이수 기준을 확인해야 한다.",
            "https://biochemistry.cnu.ac.kr/grad",
        ],
    )

    assert result.passed is True
    assert result.failures == []
    assert "unsupported_url_claim" in result.warnings
    assert "unsupported_numeric_claim" in result.warnings
    assert "unsupported_institution_claim" in result.warnings
    assert "unsupported_menu_claim" in result.warnings
    assert result.unsupported_urls == ["https://made-up.cnu.ac.kr/grad"]
    assert result.unsupported_numeric_claims == ["130점"]
    assert result.unsupported_institution_claims == ["학생지원센터"]
    assert result.unsupported_menu_claims == ["학사정보 > 졸업요건"]


def test_answer_validator_warns_but_passes_optional_url_and_numeric_claims_by_default() -> None:
    result = validate_task2_answer(
        "졸업 기준은 130학점 이상일 수 있으며 자세한 내용은 https://example.cnu.ac.kr 에서 확인하세요.",
        evidence_texts=["졸업 기준은 학과별 공식 자료에서 확인해야 한다."],
    )

    assert result.passed is True
    assert result.failures == []
    assert "unsupported_url_claim" in result.warnings
    assert "unsupported_numeric_claim" in result.warnings
    assert result.unsupported_urls == ["https://example.cnu.ac.kr"]
    assert result.unsupported_numeric_claims == ["130학점"]


def test_answer_validator_can_still_fail_optional_claims_in_strict_grounding_mode() -> None:
    result = validate_task2_answer(
        "졸업 기준은 130학점 이상입니다.",
        evidence_texts=["졸업 기준은 학과별 공식 자료에서 확인해야 한다."],
        strict_grounding=True,
    )

    assert result.passed is False
    assert "unsupported_numeric_claim" in result.failures


def test_answer_validator_allows_claims_present_in_evidence_texts() -> None:
    result = validate_task2_answer(
        "생화학과 졸업요건은 생화학과 공식 자료에서 확인하고, 전공은 130학점 이상입니다.",
        evidence_texts=[
            "생화학과 졸업요건",
            "생화학과 전공은 130학점 이상 이수해야 한다.",
        ],
    )

    assert result.passed is True
    assert result.unsupported_numeric_claims == []
    assert result.unsupported_institution_claims == []


def test_answer_validation_rejects_internal_temporal_trace_leak() -> None:
    result = validate_task2_answer("TemporalIntent confidence high 이므로 2026년 6월 16일로 답합니다.")

    assert result.passed is False
    assert "internal_trace_leak" in result.failures


def test_answer_validator_still_blocks_internal_leakage_after_policy_softening() -> None:
    internal = validate_task2_answer("근거 1과 chunk_12를 보면 TemporalIntent confidence high입니다.")
    template = validate_task2_answer("{'answer': 'system prompt fallback'}")

    assert internal.passed is False
    assert "internal_id_exposed" in internal.failures
    assert "internal_trace_leak" in internal.failures
    assert template.passed is False
    assert "raw_json_or_template_text" in template.failures
    assert "system_or_fallback_leak" in template.failures
