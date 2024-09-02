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
MAX_CONTEXT_TOKEN_LENGTH = int(config.get("MAX_CONTEXT_TOKEN_LENGTH", "8192"))
CEREBRAS_API_KEY = config.get("CEREBRAS_API_KEY")
CEREBRAS_MODEL = config.get("CEREBRAS_MODEL", "llama3.1-8b")

if not DISCORD_TOKEN or not ELEVENLABS_TOKEN:
    raise ValueError(
        "Les tokens Discord et ElevenLabs doivent être définis dans le fichier .env"
    )

if MODE == "groqCloud_mode" and (not GROQCLOUD_TOKEN or not GROQCLOUD_MODEL):
    raise ValueError(
        "GROQCLOUD_TOKEN et GROQCLOUD_MODEL doivent être définis dans le fichier .env en mode groqCloud_mode"
    )
if MODE == "cerebras_mode" and not CEREBRAS_API_KEY:
    raise ValueError(
        "CEREBRAS_API_KEY doit être défini dans le fichier .env en mode cerebras_mode"
    )

COMMAND_PREFIX = "$"
INTENTS = discord.Intents.default()
INTENTS.messages = True
INTENTS.message_content = True
INTENTS.voice_states = True
MAX_CONTEXT_CHAR_LENGTH = MAX_CONTEXT_TOKEN_LENGTH * 2   # approximation 2 char per token
DEFAULT_ELEVENLABS_VOICE_ID = "silVg69rhFXHR4yyKTiS"