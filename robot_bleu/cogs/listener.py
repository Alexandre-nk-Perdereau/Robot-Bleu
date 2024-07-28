import discord
from discord.ext import commands
from robot_bleu.utils.context_management import save_context
from robot_bleu.utils.queue_management import (
    request_queue,
    process_request_queue,
    voice_queues,
    clear_voice_queue,
)
from robot_bleu.config import DEFAULT_ELEVENLABS_VOICE_ID
from robot_bleu.utils.file_extensions import TEXT_FILE_EXTENSIONS
import asyncio

class Listener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.listening_channels = {}
        self.bot.loop.create_task(process_request_queue(self.bot))

    @commands.command(name="listen")
    async def listen(self, ctx):
        channel_id = ctx.channel.id
        channel = self.bot.get_channel(channel_id)

        if not channel:
            await ctx.send("Erreur : Le canal spécifié n'a pas été trouvé.")
            return

        if channel.id in self.bot.listening_channels:
            await ctx.send(f"J'écoute déjà le salon {channel.mention}")
            return

        try:
            if isinstance(channel, discord.TextChannel):
                self.bot.listening_channels[channel.id] = {
                    "messages": [],
                    "mode": "streaming",
                    "tts_mode": "elevenlabs",
                    "elevenlabs_voice_id": DEFAULT_ELEVENLABS_VOICE_ID,
                }
                await ctx.send(
                    f"Je vais maintenant écouter le salon {channel.mention} pour les messages textuels."
                )

            elif isinstance(channel, discord.VoiceChannel):
                vc = await channel.connect()
                self.bot.listening_channels[channel.id] = {
                    "messages": [],
                    "mode": "streaming",
                    "tts_mode": "elevenlabs",
                    "elevenlabs_voice_id": DEFAULT_ELEVENLABS_VOICE_ID,
                    "voice_client": vc,
                }
                voice_queues[channel.id] = asyncio.Queue()
                await ctx.send(
                    f"Le bot a rejoint le canal vocal {channel.mention} et écoutera maintenant."
                )

            else:
                await ctx.send(
                    "Cette commande doit être exécutée dans un canal texte ou vocal."
                )
                return

        except Exception as e:
            await ctx.send(f"Une erreur inattendue est survenue: {str(e)}")
            if channel.id in self.bot.listening_channels:
                del self.bot.listening_channels[channel.id]

    @commands.command(name="pause_listen")
    async def pause_listen(self, ctx):
        channel_id = ctx.channel.id
        channel = self.bot.get_channel(channel_id)
        if channel:
            if channel.id in self.bot.listening_channels:
                vc = self.bot.listening_channels[channel.id].get("voice_client")
                if vc:
                    await vc.disconnect()
                    await clear_voice_queue(vc.channel.id)
                del self.bot.listening_channels[channel.id]
                await ctx.send(f"J'ai mis en pause l'écoute du salon {channel.mention}")
            else:
                await ctx.send(f"Je n'écoutais pas le salon {channel.mention}")
        else:
            await ctx.send("Erreur : Le canal spécifié n'a pas été trouvé.")

    @commands.command(name="stop_listen")
    async def stop_listen(self, ctx):
        channel_id = ctx.channel.id
        channel = self.bot.get_channel(channel_id)
        if channel:
            if channel.id in self.bot.listening_channels:
                vc = self.bot.listening_channels[channel.id].get("voice_client")
                if vc:
                    await vc.disconnect()
                    await clear_voice_queue(vc.channel.id)
                del self.bot.listening_channels[channel.id]
                await save_context(channel.id, [])
                await ctx.send(
                    f"J'ai arrêté d'écouter le salon {channel.mention} et supprimé son contexte"
                )
            else:
                await ctx.send(f"Je n'écoutais pas le salon {channel.mention}")
        else:
            await ctx.send("Erreur : Le canal spécifié n'a pas été trouvé.")

    @commands.command(name="set_mode")
    async def set_mode(self, ctx, mode: str):
        channel_id = ctx.channel.id
        channel = self.bot.get_channel(channel_id)
        if channel:
            if mode.lower() in ["streaming", "non-streaming"]:
                if channel.id in self.bot.listening_channels:
                    self.bot.listening_channels[channel.id]["mode"] = mode.lower()
                    await ctx.send(
                        f"Le mode du salon {channel.mention} a été défini sur {mode.lower()}"
                    )
                else:
                    await ctx.send(f"Je n'écoute pas le salon {channel.mention}")
            else:
                await ctx.send(
                    "Mode invalide. Utilisez 'streaming' ou 'non-streaming'."
                )
        else:
            await ctx.send("Erreur : Le canal spécifié n'a pas été trouvé.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if (
            message.content.startswith(("!", "%", "$", "(ignore)"))
            or message.reference is not None
        ):
            return

        if message.channel.id in self.bot.listening_channels:
            content = await self.process_message_with_attachments(message)
            await request_queue.put(
                (content, message.channel.id)
            )

    async def process_message_with_attachments(self, message):
        content = ""
        if message.attachments:
            attachment_names = [att.filename for att in message.attachments]
            content += f"{message.author.name} a joint à son message {', '.join(attachment_names)}.\n\n"

            for attachment in message.attachments:
                if any(attachment.filename.endswith(ext) for ext in TEXT_FILE_EXTENSIONS):
                    file_content = await self.get_attachment_content(attachment)
                    content += f"**{attachment.filename}:** {file_content}\n\n"

        content += f"**{message.author.name}:** {message.content}"
        return content

    async def get_attachment_content(self, attachment):
        try:
            content = await attachment.read()
            return content.decode('utf-8')
        except UnicodeDecodeError:
            return "[Contenu binaire non affichable]"

async def setup(bot):
    await bot.add_cog(Listener(bot))
