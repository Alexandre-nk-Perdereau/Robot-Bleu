import asyncio
import discord
from discord.ext import commands
import pyttsx3
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings
from io import BytesIO

from robot_bleu.config import DEFAULT_ELEVENLABS_VOICE_ID, ELEVENLABS_TOKEN

engine = pyttsx3.init()
voices = engine.getProperty("voices")
engine.setProperty("voice", voices[0].id)

elevenlabs_client = ElevenLabs(api_key=ELEVENLABS_TOKEN)


class TTS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="set_voice")
    async def set_voice(self, ctx, voice_index: int):
        try:
            engine.setProperty("voice", voices[voice_index].id)
            await ctx.send(f"Voix définie sur : {voices[voice_index].name}")
        except IndexError:
            await ctx.send(
                f"Index de voix invalide. Veuillez choisir un index entre 0 et {len(voices) - 1}."
            )

    @commands.command(name="switch_tts")
    async def switch_tts(self, ctx):
        channel_id = ctx.channel.id
        if channel_id in self.bot.listening_channels:
            current_mode = self.bot.listening_channels[channel_id]["tts_mode"]
            new_mode = "basic" if current_mode == "elevenlabs" else "elevenlabs"
            self.bot.listening_channels[channel_id]["tts_mode"] = new_mode
            await ctx.send(f"Le mode TTS pour ce canal est maintenant : {new_mode}")
        else:
            await ctx.send(f"Je n'écoute pas le salon {ctx.channel.mention}")

    @commands.command(name="set_elevenlabs_voice")
    async def set_elevenlabs_voice(self, ctx, voice_id: str):
        channel_id = ctx.channel.id
        if channel_id in self.bot.listening_channels:
            self.bot.listening_channels[channel_id]["elevenlabs_voice_id"] = voice_id
            await ctx.send(
                f"Le voice_id ElevenLabs pour ce canal est maintenant : {voice_id}"
            )
        else:
            await ctx.send(f"Je n'écoute pas le salon {ctx.channel.mention}")

    @staticmethod
    async def elevenlabs_tts(vc, text, voice_id=DEFAULT_ELEVENLABS_VOICE_ID):
        try:
            response = elevenlabs_client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id="eleven_multilingual_v2",
                voice_settings=VoiceSettings(
                    stability=0.5,
                    similarity_boost=0.5,
                    style=0.0,
                    use_speaker_boost=True,
                ),
            )

            audio_stream = BytesIO()
            for chunk in response:
                if chunk:
                    audio_stream.write(chunk)
            audio_stream.seek(0)

            with open("response.mp3", "wb") as f:
                f.write(audio_stream.read())

            vc.play(discord.FFmpegPCMAudio("response.mp3"))
            while vc.is_playing():
                await asyncio.sleep(1)
            return True
        except Exception as e:
            print(f"Erreur lors de l'utilisation de ElevenLabs TTS: {e}")
            return False

    @staticmethod
    async def basic_tts(vc, text):
        engine.save_to_file(text, "response.mp3")
        engine.runAndWait()
        vc.play(discord.FFmpegPCMAudio("response.mp3"))
        while vc.is_playing():
            await asyncio.sleep(1)


async def setup(bot):
    await bot.add_cog(TTS(bot))
