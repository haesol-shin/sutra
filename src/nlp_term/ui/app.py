from __future__ import annotations

import argparse

from nlp_term.chat.composer import compose_answer
from nlp_term.chat.router import route_question


def answer(message: str, history: list[dict[str, str]] | None = None) -> str:
    route = route_question(message)
    return compose_answer(route)


def build_demo():
    import gradio as gr

    return gr.ChatInterface(
        fn=answer,
        title="CNU Campus ChatBot",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Gradio chatbot UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--smoke-test", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.smoke_test:
        response = answer("셔틀버스 시간표 알려줘", [])
        if not response:
            raise SystemExit("smoke test failed: empty response")
        print("ui-smoke-ok")
        return
    demo = build_demo()
    demo.launch(server_name=args.host, server_port=args.port)


if __name__ == "__main__":
    main()
