from __future__ import annotations

import os

import chainlit as cl

from sutra.errors import SutraError
from sutra.llama import EchoClient
from sutra.service import ask


@cl.on_chat_start
async def on_chat_start() -> None:
    workspace = os.environ.get("SUTRA_WORKSPACE")
    echo = os.environ.get("SUTRA_ECHO") == "1"
    cl.user_session.set("workspace", workspace)
    cl.user_session.set("echo", echo)
    cl.user_session.set("client", EchoClient() if echo else None)


@cl.on_message
async def on_message(message: cl.Message) -> None:
    client = cl.user_session.get("client")
    workspace = cl.user_session.get("workspace")

    msg = cl.Message(content="")
    await msg.send()

    try:
        answer = await cl.make_async(ask)(
            message.content,
            workspace=workspace,
            client=client,
        )
    except SutraError as e:
        msg.content = f"**Error**: {e}"
        await msg.update()
        return

    parts = [answer.answer]

    if answer.evidence:
        parts.append("\n\n---\n**Sources:**")
        for ev in answer.evidence:
            source = ev.source_name or "Unknown"
            line = f"- {source}"
            if ev.source_url:
                line += f" ([link]({ev.source_url}))"
            parts.append(line)

    msg.content = "\n".join(parts)
    await msg.update()
