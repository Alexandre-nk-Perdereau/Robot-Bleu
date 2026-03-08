from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN: str = os.environ["DISCORD_TOKEN"]
LLM_BACKEND: str = os.getenv("LLM_BACKEND", "vllm")  # "vllm" or "ollama"
_llm_host: str = os.environ["OPENAI_COMPATIBLE"]
LLM_BASE_URL: str = (
    f"https://{_llm_host}/v1" if "ollama.com" in _llm_host else f"http://{_llm_host}/v1"
)
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "not-needed")
AGENT_TICK_INTERVAL: float = float(os.getenv("AGENT_TICK_INTERVAL", "5"))
LLM_MODEL: str = os.getenv("LLM_MODEL", "Qwen/Qwen3.5-9B")
LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_MAX_THINKING_TOKENS: int = int(os.getenv("LLM_MAX_THINKING_TOKENS", "0"))
DEFAULT_PERSONA: str = os.getenv(
    "DEFAULT_PERSONA", "Tu es un assistant amical et drole."
)
