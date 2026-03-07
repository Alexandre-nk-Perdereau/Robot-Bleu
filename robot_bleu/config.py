from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN: str = os.environ["DISCORD_TOKEN"]
LLM_BASE_URL: str = f"http://{os.environ['OPENAI_COMPATIBLE']}/v1"
AGENT_TICK_INTERVAL: float = float(os.getenv("AGENT_TICK_INTERVAL", "5"))
LLM_MODEL: str = os.getenv("LLM_MODEL", "Qwen/Qwen3.5-9B")
LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_MAX_THINKING_TOKENS: int = int(os.getenv("LLM_MAX_THINKING_TOKENS", "0"))
DEFAULT_PERSONA: str = os.getenv(
    "DEFAULT_PERSONA", "Tu es un assistant amical et drole."
)
