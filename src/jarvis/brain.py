import openai

OFFLINE_MESSAGE = "My brain is offline. Is LlamaStash running?"
MAX_HISTORY = 20

SYSTEM_PROMPT = (
    "You are Jarvis, a personal voice assistant running on the user's PC. "
    "Your replies are spoken aloud, so keep them to 1-3 short sentences with no "
    "markdown or lists. Reply in the language the user writes in (English or "
    "Indonesian)."
)

LANGUAGE_NAMES = {"en": "English", "id": "Indonesian"}


class Brain:
    def __init__(self, client, model: str, extra_body: dict | None = None):
        self.client = client
        self.model = model
        self.extra_body = extra_body
        self.history: list[dict] = []

    def ask(self, text: str, lang: str | None = None) -> str:
        self.history.append({"role": "user", "content": text})
        self.history = self.history[-MAX_HISTORY:]
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": _system_prompt(lang)}]
                + self.history,
                extra_body=self.extra_body,
            )
        except openai.APIConnectionError:
            self.history.pop()
            return OFFLINE_MESSAGE
        reply = response.choices[0].message.content or ""
        self.history.append({"role": "assistant", "content": reply})
        return reply


def _system_prompt(lang: str | None) -> str:
    if lang in LANGUAGE_NAMES:
        return f"{SYSTEM_PROMPT} The user is speaking {LANGUAGE_NAMES[lang]}."
    return SYSTEM_PROMPT
