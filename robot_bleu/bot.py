"""Discord bot -- event collection and agent loop scheduling."""

from __future__ import annotations

import asyncio
import base64
import logging

import discord
from discord import app_commands
from openai import AsyncOpenAI

from . import config
from .agent import check_llm_available, run_agent_tick
from .session import SessionManager, SessionMode
from .tools import TEXT_EXTENSIONS

log = logging.getLogger(__name__)


class RobotBleu(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        intents.guilds = True
        intents.members = True
        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)
        self.sessions = SessionManager()
        self.llm_client = AsyncOpenAI(
            base_url=config.LLM_BASE_URL,
            api_key=config.LLM_API_KEY,
        )
        self._agent_task: asyncio.Task | None = None

    async def setup_hook(self) -> None:
        self._register_commands()
        self.tree.on_error = self._on_tree_error
        await self.tree.sync()
        self._agent_task = asyncio.create_task(self._agent_loop())
        log.info("Bot ready, agent loop started.")

    @staticmethod
    async def _on_tree_error(
        interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error.__cause__, discord.NotFound):
            log.debug("Interaction expired (stale command), ignoring.")
            return
        log.exception("Command error: %s", error)

    # -- Slash commands --

    def _register_commands(self) -> None:
        @self.tree.command(
            name="bleu_on", description="Activer Robot Bleu sur ce serveur/canal"
        )
        @app_commands.describe(
            mode="server (tout le serveur) ou channel (ce canal seulement)",
            persona="Personnalite / persona du bot",
        )
        @app_commands.choices(
            mode=[
                app_commands.Choice(name="server", value="server"),
                app_commands.Choice(name="channel", value="channel"),
            ]
        )
        async def bleu_on(
            interaction: discord.Interaction,
            mode: app_commands.Choice[str],
            persona: str = config.DEFAULT_PERSONA,
        ) -> None:
            await interaction.response.defer(ephemeral=True)
            if interaction.guild is None:
                await interaction.followup.send(
                    "Commande disponible uniquement dans un serveur."
                )
                return

            session_mode = SessionMode(mode.value)
            channel_id = (
                interaction.channel_id if session_mode == SessionMode.CHANNEL else None
            )
            session = self.sessions.activate(
                guild=interaction.guild,
                mode=session_mode,
                persona=persona,
                channel_id=channel_id,
            )
            scope = (
                f"canal #{interaction.channel.name}"
                if session_mode == SessionMode.CHANNEL
                else "serveur"
            )
            await interaction.followup.send(
                f"Robot Bleu active en mode **{mode.value}** sur ce {scope}.",
            )
            log.info("Session activated: %s", session.key)

        @self.tree.command(name="bleu_off", description="Desactiver Robot Bleu")
        async def bleu_off(interaction: discord.Interaction) -> None:
            await interaction.response.defer(ephemeral=True)
            if interaction.guild is None:
                await interaction.followup.send(
                    "Commande disponible uniquement dans un serveur."
                )
                return

            # Try channel first, then server
            removed = self.sessions.deactivate(
                interaction.guild.id, interaction.channel_id
            )
            if not removed:
                removed = self.sessions.deactivate(interaction.guild.id)
            if removed:
                await interaction.followup.send("Robot Bleu desactive.")
            else:
                await interaction.followup.send("Robot Bleu n'etait pas actif ici.")

        @self.tree.command(
            name="bleu_status", description="Voir le statut de Robot Bleu"
        )
        async def bleu_status(interaction: discord.Interaction) -> None:
            await interaction.response.defer(ephemeral=True)
            if interaction.guild is None:
                await interaction.followup.send(
                    "Commande disponible uniquement dans un serveur."
                )
                return

            session = self.sessions.get(interaction.guild.id, interaction.channel_id)
            if session and session.enabled:
                await interaction.followup.send(
                    f"Actif en mode **{session.mode.value}** | Persona: {session.persona[:100]}...",
                )
            else:
                await interaction.followup.send("Robot Bleu n'est pas actif ici.")

        @self.tree.command(
            name="bleu_persona", description="Changer le persona de Robot Bleu"
        )
        @app_commands.describe(persona="Nouveau persona / system prompt")
        async def bleu_persona(interaction: discord.Interaction, persona: str) -> None:
            await interaction.response.defer(ephemeral=True)
            if interaction.guild is None:
                await interaction.followup.send(
                    "Commande disponible uniquement dans un serveur."
                )
                return

            session = self.sessions.get(interaction.guild.id, interaction.channel_id)
            if session and session.enabled:
                session.persona = persona
                session.save()
                await interaction.followup.send(f"Persona mis a jour: {persona[:200]}")
            else:
                await interaction.followup.send("Robot Bleu n'est pas actif ici.")

        @self.tree.command(
            name="bleu_clear",
            description="Effacer l'historique de conversation de Robot Bleu",
        )
        async def bleu_clear(interaction: discord.Interaction) -> None:
            await interaction.response.defer(ephemeral=True)
            if interaction.guild is None:
                await interaction.followup.send(
                    "Commande disponible uniquement dans un serveur."
                )
                return

            session = self.sessions.get(interaction.guild.id, interaction.channel_id)
            if session and session.enabled:
                session.conversation_history.clear()
                session.events.clear()
                session.save()
                await interaction.followup.send("Historique efface.")
            else:
                await interaction.followup.send("Robot Bleu n'est pas actif ici.")

        @self.tree.command(
            name="bleu_history",
            description="Voir l'historique de conversation de Robot Bleu",
        )
        async def bleu_history(interaction: discord.Interaction) -> None:
            await interaction.response.defer(ephemeral=True)
            if interaction.guild is None:
                await interaction.followup.send(
                    "Commande disponible uniquement dans un serveur."
                )
                return

            session = self.sessions.get(interaction.guild.id, interaction.channel_id)
            if not session or not session.enabled:
                await interaction.followup.send("Robot Bleu n'est pas actif ici.")
                return

            if not session.conversation_history:
                await interaction.followup.send("Historique vide.")
                return

            lines: list[str] = []
            for msg in session.conversation_history[-20:]:
                role = msg["role"]
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join(p.get("text", "[image]") for p in content)
                if role == "tool":
                    content = content[:100]
                elif role == "assistant" and "tool_calls" in msg:
                    tools = ", ".join(
                        tc["function"]["name"] for tc in msg["tool_calls"]
                    )
                    content = f"[tools: {tools}] {content or ''}"
                line = f"**{role}**: {content[:200]}"
                lines.append(line)

            text = "\n".join(lines)
            if len(text) > 1900:
                text = text[-1900:]
            await interaction.followup.send(text)

    # -- Event listeners --

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user:
            return
        if message.guild is None:
            return

        log.debug(
            "on_message: %s in #%s (guild:%s, channel:%s)",
            message.author.display_name,
            message.channel.name,
            message.guild.id,
            message.channel.id,
        )
        session = self.sessions.get(message.guild.id, message.channel.id)
        if session is None or not session.enabled:
            log.debug(
                "on_message: no active session for guild:%s channel:%s",
                message.guild.id,
                message.channel.id,
            )
            return

        images_b64: list[dict[str, str]] = []
        text_files: list[dict[str, str]] = []

        for att in message.attachments:
            try:
                if att.content_type and att.content_type.startswith("image/"):
                    data = await att.read()
                    b64 = base64.b64encode(data).decode()
                    images_b64.append({"mime": att.content_type, "base64": b64})
                elif any(att.filename.lower().endswith(ext) for ext in TEXT_EXTENSIONS):
                    data = await att.read()
                    text_files.append(
                        {
                            "filename": att.filename,
                            "content": data.decode("utf-8", errors="replace"),
                        }
                    )
            except Exception:
                log.warning(
                    "Failed to download attachment %s", att.filename, exc_info=True
                )

        session.push_event(
            "message",
            author=message.author.display_name,
            content=message.content,
            channel_name=message.channel.name,
            channel_id=message.channel.id,
            message_id=message.id,
            images_b64=images_b64,
            text_files=text_files,
        )
        log.debug(
            "Event captured: %s in #%s (%d pending)",
            message.author.display_name,
            message.channel.name,
            len(session.events),
        )

    async def on_reaction_add(
        self, reaction: discord.Reaction, user: discord.User
    ) -> None:
        if user == self.user:
            return
        if reaction.message.guild is None:
            return

        session = self.sessions.get(
            reaction.message.guild.id, reaction.message.channel.id
        )
        if session is None or not session.enabled:
            return

        session.push_event(
            "reaction_add",
            user=user.display_name,
            emoji=str(reaction.emoji),
            channel_name=reaction.message.channel.name,
            channel_id=reaction.message.channel.id,
            message_id=reaction.message.id,
        )

    # -- Agent loop --

    async def _agent_loop(self) -> None:
        """Main agent loop -- runs every AGENT_TICK_INTERVAL seconds."""
        await self.wait_until_ready()
        log.info("Agent loop running (tick every %.1fs)", config.AGENT_TICK_INTERVAL)

        while not self.is_closed():
            await asyncio.sleep(config.AGENT_TICK_INTERVAL)

            if not await check_llm_available():
                continue

            for session in self.sessions.active_sessions:
                try:
                    await run_agent_tick(self, session, self.llm_client)
                except Exception:
                    log.exception("Agent tick failed for session %s", session.key)
