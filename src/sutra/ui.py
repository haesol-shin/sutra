from __future__ import annotations

import os

import chainlit as cl

from sutra.config import Config, load_config
from sutra.documents import load_documents
from sutra.errors import SutraError
from sutra.llama import EchoClient, LlamaClient
from sutra.models import Evidence
from sutra.prompts import render_prompt
from sutra.retrieval import retrieve


def _format_evidence(evidence_items: list[Evidence]) -> str:
    parts: list[str] = ["\n\n---\n### 📚 참고 문서"]
    for i, ev in enumerate(evidence_items, 1):
        title = ev.title or "Untitled"
        score_str = f" (score: {ev.score:.3f})" if ev.score is not None else ""
        source_name = ev.source_name or "Unknown"

        if ev.source_url:
            parts.append(f"\n**{i}.** [{title}]({ev.source_url}){score_str}")
        else:
            parts.append(f"\n**{i}.** {title}{score_str}")

        parts.append(f"   출처: {source_name}")

        excerpt = ev.text[:300].replace("\n", " ")
        if len(ev.text) > 300:
            excerpt += "..."
        parts.append(f"   > {excerpt}")

    return "\n".join(parts)


@cl.on_chat_start
async def on_chat_start() -> None:
    """Initialize session state on chat start."""
    workspace = os.environ.get("SUTRA_WORKSPACE")
    echo = os.environ.get("SUTRA_ECHO") == "1"
    cl.user_session.set("workspace", workspace)
    cl.user_session.set("echo", echo)
    cl.user_session.set("client", EchoClient() if echo else None)


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Handle an incoming chat message."""
    client = cl.user_session.get("client")
    workspace = cl.user_session.get("workspace")
    question = message.content

    try:
        config = (
            workspace
            if isinstance(workspace, Config)
            else load_config(workspace)
        )
    except SutraError as e:
        await cl.Message(content=f"**Error**: {e}").send()
        return

    # Step 1: Retrieval
    async with cl.Step(name="검색", type="tool") as step:
        step.input = f"'{question}'에 대한 문서 검색 중..."
        try:
            documents = await cl.make_async(load_documents)(config)
            evidence = await cl.make_async(retrieve)(question, documents, config)
            step.output = f"{len(evidence.items)}개 문서 검색 완료"
        except Exception as e:
            step.output = f"검색 실패: {e}"
            await cl.Message(content="**Error**: 검색 중 오류가 발생했습니다.").send()
            return
        finally:
            pass

    if not evidence.items:
        msg = cl.Message(
            content="I do not have enough evidence in this workspace to answer."
        )
        await msg.send()
        return

    # Step 2: Analysis
    async with cl.Step(name="분석", type="tool") as step:
        step.input = "문서 분석 중..."
        try:
            prompt = await cl.make_async(render_prompt)(question, evidence, config)
            step.output = f"{len(evidence.items)}개 문서 분석 완료"
        except Exception as e:
            step.output = f"분석 실패: {e}"
            await cl.Message(content="**Error**: 문서 분석 중 오류가 발생했습니다.").send()
            return
        finally:
            pass

    # Step 3: Generation
    async with cl.Step(name="응답 생성", type="llm") as step:
        step.input = "응답 생성 중..."
        try:
            llm = client or LlamaClient(
                config.runtime.base_url,
                timeout_seconds=config.runtime.timeout_seconds,
            )
            result = await cl.make_async(llm.chat)(
                prompt.messages,
                model=config.runtime.model,
                temperature=config.runtime.temperature,
                max_tokens=config.runtime.max_tokens,
            )
            step.output = result.content
        except Exception as e:
            step.output = f"응답 생성 실패: {e}"
            await cl.Message(content="**Error**: 응답 생성 중 오류가 발생했습니다.").send()
            return
        finally:
            pass

    parts = [result.content]
    if evidence.items:
        parts.append(_format_evidence(evidence.items))

    msg = cl.Message(content="\n".join(parts))
    await msg.send()
