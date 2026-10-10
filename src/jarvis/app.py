import argparse

import openai

from jarvis import config
from jarvis.brain import Brain
from jarvis.tools import TOOLS

EXIT_WORDS = {"exit", "quit"}
YES_WORDS = {"y", "yes", "ya", "iya"}


def is_yes(answer: str) -> bool:
    """Only a clear yes counts; anything unclear is a no."""
    return answer.strip().lower().strip(".!, ") in YES_WORDS


def confirm_in_terminal(question: str) -> bool:
    return is_yes(input(f"jarvis> Run {question}? [y/N] "))


def main() -> None:
    parser = argparse.ArgumentParser(prog="jarvis", description="Local assistant.")
    parser.add_argument(
        "--no-voice",
        action="store_true",
        help="typed input only (voice is not built yet, so this is the only mode)",
    )
    parser.parse_args()

    client = openai.OpenAI(
        base_url=config.BASE_URL,
        api_key=config.API_KEY,
        max_retries=config.MAX_RETRIES,
    )
    brain = Brain(
        client,
        config.MODEL,
        tools=TOOLS,
        confirm=confirm_in_terminal,
        extra_body=config.EXTRA_BODY,
    )

    print("Jarvis is ready. Type 'exit' to quit.")
    try:
        while True:
            text = input("you> ").strip()
            if text.lower() in EXIT_WORDS:
                break
            if text:
                print(f"jarvis> {brain.ask(text)}")
    except EOFError, KeyboardInterrupt:
        print()
