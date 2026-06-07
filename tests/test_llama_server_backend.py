from __future__ import annotations

import pytest

from nlp_term.chat.llama_server_backend import (
    LlamaServerUnavailable,
    check_llama_server_health,
    generate_with_llama_server,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> dict[str, object]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(self.text)


def test_generate_with_llama_server_reads_content_from_openai_compatible_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        assert url == "http://127.0.0.1:8080/v1/chat/completions"
        assert json["temperature"] == 0.2
        return FakeResponse(
            200,
            {"choices": [{"message": {"content": "공식 학사일정 페이지에서 확인하면 됩니다."}}]},
        )

    monkeypatch.setattr("requests.post", fake_post)

    answer = generate_with_llama_server(
        prompt="질문: 수강신청 일정은?",
        base_url="http://127.0.0.1:8080",
        timeout_seconds=5,
    )

    assert answer == "공식 학사일정 페이지에서 확인하면 됩니다."


def test_llama_server_base_url_trailing_slash_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        assert url == "http://127.0.0.1:8080/v1/chat/completions"
        return FakeResponse(200, {"choices": [{"message": {"content": "정상 답변"}}]})

    monkeypatch.setattr("requests.post", fake_post)

    assert generate_with_llama_server(prompt="질문", base_url="http://127.0.0.1:8080/") == "정상 답변"


def test_generate_with_llama_server_does_not_fallback_on_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        raise OSError("connection refused")

    monkeypatch.setattr("requests.post", fake_post)

    with pytest.raises(LlamaServerUnavailable, match="connection refused"):
        generate_with_llama_server(prompt="질문", base_url="http://127.0.0.1:8080")


def test_generate_with_llama_server_rejects_malformed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        return FakeResponse(200, {"choices": []})

    monkeypatch.setattr("requests.post", fake_post)

    with pytest.raises(LlamaServerUnavailable, match="malformed"):
        generate_with_llama_server(prompt="질문", base_url="http://127.0.0.1:8080")


def test_check_llama_server_health_uses_health_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, timeout: int) -> FakeResponse:
        assert url == "http://127.0.0.1:8080/health"
        return FakeResponse(200, {"status": "ok"})

    monkeypatch.setattr("requests.get", fake_get)

    assert check_llama_server_health("http://127.0.0.1:8080") is True
