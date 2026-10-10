import argparse

import openai

from jarvis import config, tts
from jarvis.brain import Brain
from jarvis.tools import TOOLS

EXIT_WORDS = {"exit", "quit"}
YES_WORDS = {"y", "yes", "ya", "iya"}


def is_yes(answer: str) -> bool:
    """Only a clear yes counts; anything unclear is a no."""
    return answer.strip().lower().strip(".!, ") in YES_WORDS


def confirm_in_terminal(question: str) -> bool:
    return is_yes(input(f"jarvis> Run {question}? [y/N] "))


def load_voice() -> bool:
    try:
        tts.load()
    except Exception as error:  # noqa: BLE001 - any voice problem means text only
        print(f"Voice is off ({error}). Replies will be text only.")
        return False
    return True


def speak_reply(reply: str) -> bool:
    try:
        tts.speak(reply, tts.guess_lang(reply))
    except Exception as error:  # noqa: BLE001 - audio trouble must not end the chat
        print(f"(voice stopped: {error})")
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(prog="jarvis", description="Local assistant.")
    parser.add_argument(
        "--no-voice",
        action="store_true",
        help="print replies only, do not speak them",
    )
    args = parser.parse_args()

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

    voice_on = False if args.no_voice else load_voice()

    print("Jarvis is ready. Type 'exit' to quit.")
    try:
        while True:
            text = input("you> ").strip()
            if text.lower() in EXIT_WORDS:
                break
            if text:
                reply = brain.ask(text)
                print(f"jarvis> {reply}")
                if voice_on:
                    voice_on = speak_reply(reply)
    except EOFError, KeyboardInterrupt:
        print()
