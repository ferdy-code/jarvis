import argparse
import re
import threading
import time
from contextlib import ExitStack

import numpy as np
import openai

from jarvis import config, memory_tools, stt, trace, tts, wake
from jarvis.brain import Brain
from jarvis.facts import Facts
from jarvis.history import History
from jarvis.mic import open_stream
from jarvis.tools import TOOLS

EXIT_WORDS = {"exit", "quit"}
# Whisper hears a spoken "ya" as "Yeah.", so that counts too.
YES_WORDS = {"y", "yes", "yeah", "ya", "iya"}
FAILURES_BEFORE_GIVING_UP = 3

SPOKEN_QUESTION = {
    "en": "Do you want me to run {action}? Say yes or no.",
    "id": "Apakah Anda ingin saya menjalankan {action}? Katakan ya atau tidak.",
}


# "Hey Jarvis" is heard again at the start of the recorded command; take it off.
WAKE_PHRASE = re.compile(
    r"^[ ,.!?]*(?:(?:hey|hi|hello|okay|ok|hai|halo)[ ,.!?]+)?j[ae]rvis[ ,.!?]*",
    re.IGNORECASE,
)


def without_wake_phrase(text: str) -> str:
    previous = None
    while previous != text:
        previous = text
        text = WAKE_PHRASE.sub("", text, count=1)
    return text.strip()


def is_yes(answer: str) -> bool:
    """Only a clear yes counts; anything unclear is a no."""
    return answer.strip().lower().strip(".!, ") in YES_WORDS


def confirm_in_terminal(question: str) -> bool:
    return is_yes(input(f"jarvis> Run {question}? [y/N] "))


def chime(wait: bool = False) -> None:
    """A short beep that says 'I am listening'. `wait` plays it to the end first."""
    import sounddevice

    rate = 44100
    t = np.linspace(0, 0.12, int(rate * 0.12), endpoint=False)
    tone = 0.2 * np.sin(2 * np.pi * 880 * t) * np.hanning(len(t))  # fades, no click
    sounddevice.play(tone.astype(np.float32), rate)
    if wait:
        sounddevice.wait()


class Assistant:
    """Runs typed and spoken turns one at a time, with the right kind of confirmation."""

    def __init__(
        self,
        make_brain,
        speak=None,
        listen=None,
        wait_for_wake=None,
        chime=None,
        ask_terminal=confirm_in_terminal,
        open_mic=open_stream,
        trace_path=None,
    ):
        self.lock = threading.Lock()  # one turn at a time, so speech never overlaps
        self.source = "typed"  # where the current turn came from
        self.lang = "en"  # language of the last spoken request
        self.speak = speak
        self.listen = listen
        self.wait_for_wake = wait_for_wake
        self.chime = chime
        self.ask_terminal = ask_terminal
        self.open_mic = open_mic
        self.trace_path = trace_path  # where each turn is logged; None means nowhere
        self.brain = make_brain(self.confirm)

    def confirm(self, question: str) -> bool:
        """Ask the way the request came in: on the terminal, or aloud."""
        with trace.span("confirm", action=question, source=self.source) as span:
            answer = self._ask_confirmation(question)
            span.set(answer=answer)
        return answer

    def _ask_confirmation(self, question: str) -> bool:
        if self.source != "voice":
            return self.ask_terminal(question)
        action = " ".join(re.sub(r"[()=_,]", " ", question).split())
        spoken = SPOKEN_QUESTION[self.lang].format(action=action)
        print(f"jarvis> {spoken}")
        self._say(spoken, self.lang)
        self.chime(wait=True)  # your turn; done before the microphone opens
        text, _lang = self.listen()
        print(f"you (voice)> {text or '(heard nothing)'}")
        return is_yes(text)

    def reply_to(self, text: str, source: str) -> None:
        with self.lock:
            self.source = source
            with trace.turn(self.trace_path, source) as turn:
                turn.set(text=text)
                reply = self.brain.ask(text)
                turn.set(reply=reply)
                print(f"jarvis> {reply}")
                self._say(reply)

    def _say(self, text: str, lang: str | None = None) -> None:
        if self.speak is None:
            return
        try:
            self.speak(text, lang)
        except Exception as error:  # noqa: BLE001 - audio trouble must not end the chat
            print(f"(voice stopped: {error})")
            self.speak = None

    def voice_once(self) -> None:
        """One spoken turn: wake word, chime, listen, answer."""
        # One open microphone from the wake word to the end of the command, so
        # nothing said right after "Hey Jarvis" is lost. It is closed before
        # Jarvis answers, so it does not record its own voice.
        with ExitStack() as stack, self.open_mic() as mic:
            self.wait_for_wake(mic)
            if self.lock.locked():
                return  # Jarvis is talking, so this was most likely its own voice
            # The trace starts at the wake word and outlives the microphone, so it also
            # shows wake words that led to nothing, and how long recording and
            # transcribing took.
            turn = stack.enter_context(trace.turn(self.trace_path, "voice"))
            print("(wake word heard - speak now)")
            self.chime()
            heard, lang = self.listen(mic, after_wake=True)
            mic_closed = stack.pop_all()  # hand the open turn on, past the microphone
        with mic_closed:
            text = without_wake_phrase(heard)
            turn.set(heard=heard, lang=lang)
            if not text:
                print("(heard nothing)")
                return
            self.lang = lang
            print(f"you (voice)> {text}")
            self.reply_to(text, "voice")

    def voice_loop(self) -> None:
        failures = 0
        while True:
            try:
                self.voice_once()
                failures = 0
            except Exception as error:  # noqa: BLE001 - a glitch must not kill the thread
                failures += 1
                print(f"(voice input problem: {error})")
                if failures >= FAILURES_BEFORE_GIVING_UP:
                    print("Voice input is off. You can still type.")
                    return
                time.sleep(2)

    def typed_loop(self) -> None:
        while True:
            text = input("you> ").strip()
            if text.lower() in EXIT_WORDS:
                return
            if text:
                self.reply_to(text, "typed")


def load_speaker():
    """The function that speaks a reply, or None if the voice cannot be used."""
    try:
        tts.load()
    except Exception as error:  # noqa: BLE001 - any voice problem means text only
        print(f"Voice is off ({error}). Replies will be text only.")
        return None
    return lambda text, lang=None: tts.speak(text, lang or tts.guess_lang(text))


def load_microphone() -> bool:
    """Load Whisper and the wake word; False means no voice input."""
    try:
        stt.load()
        wake.load()
        peak = stt.mic_peak()
    except Exception as error:  # noqa: BLE001 - any microphone problem means typing only
        print(f"Voice input is off ({error}). You can still type.")
        return False
    if peak == 0.0:  # a quiet room is never exactly zero; a blocked microphone is
        print("Warning: the microphone gives no signal at all. Check that it is not")
        print("blocked under Settings > Privacy > Microphone.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(prog="jarvis", description="Local assistant.")
    parser.add_argument(
        "--no-voice",
        action="store_true",
        help="typed input and printed replies only: no wake word, no speaking",
    )
    args = parser.parse_args()

    client = openai.OpenAI(
        base_url=config.BASE_URL,
        api_key=config.API_KEY,
        max_retries=config.MAX_RETRIES,
    )
    speak, listening = None, False
    if not args.no_voice:
        print("Loading the voice and listening models (about 6 s)...")
        speak = load_speaker()
        listening = load_microphone()

    tools, facts = TOOLS, None
    if config.DB_FILE:
        store = Facts(config.DB_FILE)
        tools, facts = {**TOOLS, **memory_tools.build(store)}, store.all

    assistant = Assistant(
        make_brain=lambda confirm: Brain(
            client,
            config.MODEL,
            tools=tools,
            confirm=confirm,
            extra_body=config.EXTRA_BODY,
            history=History(config.DB_FILE) if config.DB_FILE else None,
            facts=facts,
        ),
        speak=speak,
        listen=stt.listen,
        wait_for_wake=wake.wait_for_wake_word,
        chime=chime,
        trace_path=config.TRACE_FILE,
    )
    if listening:
        threading.Thread(target=assistant.voice_loop, daemon=True).start()
        print("Jarvis is ready. Say 'Hey Jarvis' or type. Type 'exit' to quit.")
    else:
        print("Jarvis is ready. Type 'exit' to quit.")
    try:
        assistant.typed_loop()
    except EOFError, KeyboardInterrupt:
        print()
