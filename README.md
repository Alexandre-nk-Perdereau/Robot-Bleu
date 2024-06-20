# Robot Bleu

Robot Bleu is a Discord conversational bot using the Ollama API. It provides both text and voice interaction capabilities, making it a versatile tool for Discord servers.

## Features

- Text-based conversation in Discord channels
- Voice output in Discord voice channels
- Streaming and non-streaming response modes
- Integration with Ollama for AI-powered responses
- Text-to-speech capabilities using both pyttsx3 (local) and ElevenLabs (non-local API)
- Customizable voice settings
- Context management for maintaining conversation history

## Prerequisites

- Python 3.10 or higher
- Poetry for dependency management
- Ollama API running locally
- Discord Bot Token
- ElevenLabs API Token (for advanced TTS features)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/robot-bleu.git
   cd robot-bleu
   ```

2. Install dependencies using Poetry:
   ```
   poetry install
   ```

3. Create a `.env` file in the project root and add your Discord and ElevenLabs tokens:
   ```
   DISCORD_TOKEN=your_discord_token_here
   ELEVENLABS_TOKEN=your_elevenlabs_token_here
   ```

## Usage

To start the bot, run:

```
poetry run start-bot
```

### Available Commands

- `$listen`: Start listening in a text or voice channel
- `$pause_listen`: Pause listening in the current channel
- `$stop_listen`: Stop listening and clear context in the current channel
- `$set_mode [streaming/non-streaming]`: Set the response mode
- `$set_voice [index]`: Set the voice for basic TTS
- `$switch_tts`: Switch between basic and ElevenLabs TTS
- `$set_elevenlabs_voice [voice_id]`: Set the ElevenLabs voice
- `$refresh_model`: Refresh the Ollama model

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Discord.py](https://github.com/Rapptz/discord.py) for the Discord API wrapper
- [Ollama](https://ollama.ai/) for the AI model backend
- [ElevenLabs](https://elevenlabs.io/) for advanced text-to-speech capabilities
