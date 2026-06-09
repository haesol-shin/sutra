from __future__ import annotations

import pytest

from sutra.models import Message
from sutra.errors import LlamaError
from sutra.llama import LlamaClient


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


def test_llama_client_reads_openai_compatible_chat_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        assert url == "http://127.0.0.1:8080/v1/chat/completions"
        assert json["model"] == "qwen"
        assert json["messages"] == [{"role": "user", "content": "질문"}]
        return FakeResponse(
            200,
            {
                "model": "qwen",
                "choices": [{"message": {"content": "답변"}}],
                "usage": {"total_tokens": 3},
            },
        )

    monkeypatch.setattr("requests.post", fake_post)

    result = LlamaClient("http://127.0.0.1:8080/").chat(
        [Message(role="user", content="질문")],
        model="qwen",
    )

    assert result.content == "답변"
    assert result.model == "qwen"
    assert result.usage == {"total_tokens": 3}


def test_llama_client_rejects_malformed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        return FakeResponse(200, {"choices": []})

    monkeypatch.setattr("requests.post", fake_post)

    with pytest.raises(LlamaError, match="malformed"):
        LlamaClient().chat([{"role": "user", "content": "질문"}])


def test_llama_client_health_uses_health_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, timeout: int) -> FakeResponse:
        assert url == "http://127.0.0.1:8080/health"
        return FakeResponse(200, {"status": "ok"})

    monkeypatch.setattr("requests.get", fake_get)

    assert LlamaClient("http://127.0.0.1:8080").health() is True
