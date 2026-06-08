from __future__ import annotations

from nlp_term.chat.tool_use_experiment import (
    EvidenceBlock,
    ToolExperimentTools,
    UrlCandidate,
    parse_planner_action,
    run_tool_use_experiment,
)


def test_experiment_runs_multi_step_planner_writer_with_separate_contexts() -> None:
    planner_outputs = iter(
        [
            '{"action":"official_url_search","query":"충남대학교 학생생활관","scope":"all_cnu"}',
            '{"action":"official_page_extract","candidate_id":"c1"}',
            '{"action":"answer_now"}',
        ]
    )
    writer_prompts: list[str] = []

    def planner(prompt: str) -> str:
        assert "도구 목록" in prompt
        return next(planner_outputs)

    def writer(prompt: str) -> str:
        writer_prompts.append(prompt)
        assert "학생생활관 공식 안내" in prompt
        assert "official_url_search" not in prompt
        assert "private_notes" not in prompt
        return "학생생활관 관련 안내는 학생생활관 공식 안내를 확인하면 됩니다. https://dorm.cnu.ac.kr/"

    tools = ToolExperimentTools(
        official_url_search=lambda query, scope: [
            UrlCandidate(
                candidate_id="c1",
                url="https://dorm.cnu.ac.kr/",
                title="학생생활관 공식 안내",
                snippet="학생생활관 안내",
            )
        ],
        official_page_extract=lambda candidate: [
            EvidenceBlock(
                source_url=candidate.url,
                title=candidate.title,
                text="학생생활관 공식 안내 https://dorm.cnu.ac.kr/",
                page_archetype="official_page",
            )
        ],
    )

    result = run_tool_use_experiment(
        question="학생생활관 안내 어디서 볼 수 있어요?",
        planner=planner,
        writer=writer,
        tools=tools,
        max_steps=4,
    )

    assert result.answer.startswith("학생생활관 관련 안내")
    assert result.trace.final_status == "answered"
    assert [step.action for step in result.trace.steps] == [
        "official_url_search",
        "official_page_extract",
        "answer_now",
    ]
    assert result.trace.generated_url_count == 0
    assert len(writer_prompts) == 1


def test_freeform_planner_extracts_final_json_block() -> None:
    action = parse_planner_action(
        """
        먼저 공식 사이트를 넓게 찾는다.

        ```json
        {"action":"official_url_search","query":"교내 대회","scope":"all_cnu","private_notes":"hidden"}
        ```
        """,
        variant="freeform_json",
    )

    assert action.action == "official_url_search"
    assert action.query == "교내 대회"
    assert action.private_notes == "hidden"


def test_generated_url_fetch_is_recorded_and_blocked_when_candidate_only() -> None:
    def planner(_: str) -> str:
        return '{"action":"official_page_extract","url":"https://example.com/not-official"}'

    result = run_tool_use_experiment(
        question="도서관 안내 알려줘",
        planner=planner,
        writer=lambda prompt: "사용되지 않음",
        max_steps=3,
        allow_direct_url_fetch=False,
    )

    assert result.answer == ""
    assert result.trace.final_status == "blocked_generated_url"
    assert result.trace.generated_url_count == 1
    assert result.trace.steps[0].status == "blocked"


def test_max_steps_is_experimental_parameter_and_stops_loop() -> None:
    calls = 0

    def planner(_: str) -> str:
        nonlocal calls
        calls += 1
        return '{"action":"rag_search","query":"계속 검색"}'

    result = run_tool_use_experiment(
        question="계속 검색해야 하는 질문",
        planner=planner,
        writer=lambda prompt: "사용되지 않음",
        max_steps=2,
    )

    assert calls == 2
    assert result.trace.final_status == "max_steps_exceeded"
    assert len(result.trace.steps) == 2


def test_writer_tool_call_attempt_is_recorded() -> None:
    def planner(_: str) -> str:
        return '{"action":"answer_now"}'

    def writer(_: str) -> str:
        return '{"action":"official_url_search","query":"공지"}'

    result = run_tool_use_experiment(
        question="최근 공지 알려줘",
        planner=planner,
        writer=writer,
        max_steps=1,
    )

    assert result.trace.final_status == "answered"
    assert result.trace.writer_tool_call_attempt
    assert result.trace.validation_failures == ["raw_json_or_template_text"]
