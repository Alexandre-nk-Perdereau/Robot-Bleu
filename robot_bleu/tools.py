"""Agent tools -- actions the LLM can invoke via tool_calls."""

from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import PurePosixPath
from typing import Any

import discord
from ddgs import DDGS

from .session import IdMapper

log = logging.getLogger(__name__)

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "Send a message in a Discord channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "integer",
                        "description": "The Discord channel ID to send to.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The message content.",
                    },
                },
                "required": ["channel_id", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "react_to_message",
            "description": "Add a single emoji reaction to a specific message. Only one emoji per call. Call multiple times to add multiple reactions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "integer",
                        "description": "The channel containing the message.",
                    },
                    "message_id": {
                        "type": "integer",
                        "description": "The message ID to react to.",
                    },
                    "emoji": {
                        "type": "string",
                        "description": "The emoji to react with (unicode emoji or custom emoji string).",
                    },
                },
                "required": ["channel_id", "message_id", "emoji"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web using DuckDuckGo and return results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default 5).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_users",
            "description": "List online/offline users. Without channel_id, lists all server members. With channel_id, lists members who can see that channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "integer",
                        "description": "Optional channel ID to list only members of that channel.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_channels",
            "description": "List all text channels in the current server with their IDs.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_messages",
            "description": "Read recent messages from a Discord channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "integer",
                        "description": "The channel ID to read from.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of messages to fetch (default 10, max 50).",
                    },
                },
                "required": ["channel_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_attachment",
            "description": "Download and read the content of a message attachment (image or text file). For images, returns the visual content. For text files, returns the text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "integer",
                        "description": "The channel containing the message.",
                    },
                    "message_id": {
                        "type": "integer",
                        "description": "The message ID containing the attachment.",
                    },
                    "attachment_index": {
                        "type": "integer",
                        "description": "Index of the attachment (0 for first, default 0).",
                    },
                },
                "required": ["channel_id", "message_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "do_nothing",
            "description": "Explicitly choose to do nothing this tick. Use when there is nothing interesting to respond to.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


ToolResult = str | list[dict[str, Any]]


async def execute_tool(
    bot: discord.Client,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    guild_id: int,
    channel_ids: IdMapper,
    message_ids: IdMapper,
) -> ToolResult:
    """Execute a tool call and return a text or multimodal result for the LLM."""
    # Translate short IDs back to real Discord IDs
    if "channel_id" in arguments:
        real = channel_ids.to_real(arguments["channel_id"])
        if real is None:
            return f"Unknown channel_id: {arguments['channel_id']}"
        arguments["channel_id"] = real
    if "message_id" in arguments:
        real = message_ids.to_real(arguments["message_id"])
        if real is None:
            return f"Unknown message_id: {arguments['message_id']}"
        arguments["message_id"] = real

    try:
        match tool_name:
            case "send_message":
                return await _send_message(bot, **arguments)
            case "react_to_message":
                return await _react_to_message(bot, **arguments)
            case "web_search":
                return await _web_search(**arguments)
            case "list_users":
                return await _list_users(bot, guild_id=guild_id, **arguments)
            case "list_channels":
                return _list_channels(bot, guild_id=guild_id, channel_ids=channel_ids)
            case "read_messages":
                return await _read_messages(
                    bot,
                    guild_id=guild_id,
                    channel_ids=channel_ids,
                    message_ids=message_ids,
                    **arguments,
                )
            case "fetch_attachment":
                return await _fetch_attachment(bot, guild_id=guild_id, **arguments)
            case "do_nothing":
                return "OK, doing nothing."
            case _:
                return f"Unknown tool: {tool_name}"
    except Exception as e:
        log.exception("Tool %s failed", tool_name)
        return f"Error executing {tool_name}: {e}"


async def _send_message(bot: discord.Client, channel_id: int, content: str) -> str:
    channel = bot.get_channel(channel_id)
    if channel is None:
        return f"Channel {channel_id} not found."
    await channel.send(content)
    return f"Message sent to #{channel.name}."


async def _react_to_message(
    bot: discord.Client, channel_id: int, message_id: int, emoji: str
) -> str:
    channel = bot.get_channel(channel_id)
    if channel is None:
        return f"Channel {channel_id} not found."
    message = await channel.fetch_message(message_id)
    await message.add_reaction(emoji)
    return f"Reacted with {emoji}."


def _list_channels(bot: discord.Client, guild_id: int, channel_ids: IdMapper) -> str:
    guild = bot.get_guild(guild_id)
    if guild is None:
        return "Server not found."
    bot_member = guild.me
    lines = [
        f"- #{ch.name} (id:{channel_ids.to_short(ch.id)})"
        for ch in guild.text_channels
        if ch.permissions_for(bot_member).read_messages
    ]
    if not lines:
        return "No text channels found."
    return f"Channels in {guild.name}:\n" + "\n".join(lines)


async def _list_users(
    bot: discord.Client, guild_id: int, channel_id: int | None = None
) -> str:
    guild = bot.get_guild(guild_id)
    if guild is None:
        return "Server not found."
    if channel_id is not None:
        channel = bot.get_channel(channel_id)
        if channel is None or channel.guild.id != guild_id:
            return f"Channel {channel_id} not found on this server."
        members = channel.members
        scope = f"#{channel.name}"
    else:
        members = guild.members
        scope = guild.name

    lines = []
    for m in members:
        if m.bot:
            continue
        status = str(m.status) if hasattr(m, "status") else "unknown"
        lines.append(f"- {m.display_name} ({status})")

    if not lines:
        return f"No users found in {scope}."
    return f"Users in {scope}:\n" + "\n".join(lines)


async def _read_messages(
    bot: discord.Client,
    guild_id: int,
    channel_id: int,
    channel_ids: IdMapper,
    message_ids: IdMapper,
    limit: int = 10,
) -> str:
    channel = bot.get_channel(channel_id)
    if channel is None or channel.guild.id != guild_id:
        return "Channel not found on this server."
    limit = min(limit, 50)
    messages = [msg async for msg in channel.history(limit=limit)]
    if not messages:
        return f"No messages in #{channel.name}."
    lines = []
    for msg in reversed(messages):
        author = msg.author.display_name
        mid = message_ids.to_short(msg.id)
        parts = []
        if msg.content:
            parts.append(msg.content[:300])
        for i, att in enumerate(msg.attachments):
            if att.content_type and att.content_type.startswith("image/"):
                parts.append(f"[image: {att.filename}, msg_id:{mid}, index:{i}]")
            else:
                parts.append(f"[fichier: {att.filename}, msg_id:{mid}, index:{i}]")
        for embed in msg.embeds:
            title = embed.title or ""
            desc = (embed.description or "")[:100]
            parts.append(f"[embed: {title} - {desc}]")
        lines.append(f"- {author} (msg_id:{mid}): {' '.join(parts) or '[vide]'}")
    return f"Recent messages in #{channel.name}:\n" + "\n".join(lines)


TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".py",
    ".js",
    ".ts",
    ".json",
    ".csv",
    ".xml",
    ".html",
    ".css",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".log",
    ".sh",
    ".sql",
    ".rs",
    ".go",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".rb",
    ".lua",
    ".r",
}


async def _fetch_attachment(
    bot: discord.Client,
    guild_id: int,
    channel_id: int,
    message_id: int,
    attachment_index: int = 0,
) -> ToolResult:
    channel = bot.get_channel(channel_id)
    if channel is None or channel.guild.id != guild_id:
        return f"Channel {channel_id} not found on this server."
    message = await channel.fetch_message(message_id)
    if not message.attachments:
        return "This message has no attachments."
    if attachment_index >= len(message.attachments):
        return f"Attachment index {attachment_index} out of range (message has {len(message.attachments)})."

    att = message.attachments[attachment_index]
    data = await att.read()

    if att.content_type and att.content_type.startswith("image/"):
        b64 = base64.b64encode(data).decode()
        mime = att.content_type
        return [
            {"type": "text", "text": f"Image {att.filename} from #{channel.name}:"},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]

    ext = PurePosixPath(att.filename).suffix.lower()
    if ext in TEXT_EXTENSIONS:
        try:
            text = data.decode("utf-8", errors="replace")
            return f"File {att.filename}:\n{text[:3000]}"
        except Exception:
            return f"Could not decode {att.filename} as text."

    return f"Unsupported file type: {att.filename} ({att.content_type})"


async def _web_search(query: str, max_results: int = 5) -> str:
    def _search() -> list:
        return DDGS().text(query, max_results=max_results)

    results = await asyncio.get_event_loop().run_in_executor(None, _search)
    if not results:
        return "No results found."
    formatted = []
    for r in results:
        formatted.append(f"- {r['title']}: {r['body']} ({r['href']})")
    return "\n".join(formatted)
