import os
from urllib.parse import urlparse

BASE_URL = os.environ.get("JARVIS_BASE_URL", "http://127.0.0.1:11435/v1")
MODEL = os.environ.get("JARVIS_MODEL", "Qwen3.5-4B-Q4_K_M")
API_KEY = os.environ.get("JARVIS_API_KEY", "llamastash")

# Only llama.cpp understands this flag; a hosted API would reject it.
IS_LOCAL = urlparse(BASE_URL).hostname in {"127.0.0.1", "localhost"}
MAX_RETRIES = 0 if IS_LOCAL else 2  # retrying a dead local server only adds delay
EXTRA_BODY = {"chat_template_kwargs": {"enable_thinking": False}} if IS_LOCAL else None
