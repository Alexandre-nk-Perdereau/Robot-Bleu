import os
from dotenv import dotenv_values
import discord

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
config = dotenv_values(env_path)

DISCORD_TOKEN = config.get("DISCORD_TOKEN")
ELEVENLABS_TOKEN = config.get("ELEVENLABS_TOKEN")
MODE = config.get("MODE", "ollama_mode")
GROQCLOUD_TOKEN = config.get("GROQCLOUD_TOKEN")
GROQCLOUD_MODEL = config.get("GROQCLOUD_MODEL")

OLLAMA_HOST = config.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = config.get("OLLAMA_MODEL", "RobotBleu")
OLLAMA_CONTEXT_SIZE = int(config.get("OLLAMA_CONTEXT_SIZE", "131072"))

if not DISCORD_TOKEN or not ELEVENLABS_TOKEN:
    raise ValueError(
        "Les tokens Discord et ElevenLabs doivent être définis dans le fichier .env"
    )

if MODE == "groqCloud_mode" and (not GROQCLOUD_TOKEN or not GROQCLOUD_MODEL):
    raise ValueError(
        "GROQCLOUD_TOKEN et GROQCLOUD_MODEL doivent être définis dans le fichier .env en mode groqCloud_mode"
    )

COMMAND_PREFIX = "$"
INTENTS = discord.Intents.default()
INTENTS.messages = True
INTENTS.message_content = True
INTENTS.voice_states = True
MAX_CONTEXT_LENGTH = OLLAMA_CONTEXT_SIZE * 2
DEFAULT_ELEVENLABS_VOICE_ID = "silVg69rhFXHR4yyKTiS"