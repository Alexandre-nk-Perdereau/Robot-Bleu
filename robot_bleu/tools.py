"""Agent tools -- actions the LLM can invoke via tool_calls."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import discord
from ddgs import DDGS

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
            "name": "do_nothing",
            "description": "Explicitly choose to do nothing this tick. Use when there is nothing interesting to respond to.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]

async def execute_tool(
    bot: discord.Client,
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    """Execute a tool call and return a result string for the LLM."""
    try:
        match tool_name:
            case "send_message":
                return await _send_message(bot, **arguments)
            case "react_to_message":
                return await _react_to_message(bot, **arguments)
            case "web_search":
                return await _web_search(**arguments)
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
