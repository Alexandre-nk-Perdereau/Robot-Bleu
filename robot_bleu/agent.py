"""Agent loop -- periodically processes events via the LLM."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import discord
import httpx
from openai import AsyncOpenAI

from . import config
from .session import Event, Session, SessionManager
from .tools import TOOL_DEFINITIONS, execute_tool

log = logging.getLogger(__name__)


def _build_system_prompt(session: Session) -> str:
    parts = [session.persona]
    parts.append(f"\nTu es sur le serveur Discord \"{session.guild_name}\".")
    if session.channel_names:
        parts.append(f"Canaux disponibles: {', '.join(session.channel_names)}")
    parts.append(
        "\nTu recois periodiquement des evenements Discord (nouveaux messages, reactions, etc). "
        "A chaque tick, tu decides quoi faire: repondre, reagir avec un emoji, chercher sur le web, ou ne rien faire. "
        "Tu n'es pas oblige de repondre a chaque message. Sois naturel et contextuel. "
        "IMPORTANT: Tu ne peux communiquer qu'en utilisant les outils. "
        "Pour envoyer un message, utilise TOUJOURS l'outil send_message. "
        "Le texte que tu ecris en dehors des appels d'outils n'est PAS visible par les utilisateurs."
    )
    return "\n".join(parts)


def _build_events_content(events: list[Event]) -> list[dict[str, Any]]:
    """Build a list of OpenAI content parts (text + images) from events."""
    if not events:
        return [{"type": "text", "text": "(Aucun nouvel evenement)"}]

    text_lines: list[str] = []
    content_parts: list[dict[str, Any]] = []

    for ev in events:
        ts = time.strftime("%H:%M:%S", time.localtime(ev.timestamp))
        match ev.kind:
            case "message":
                author = ev.data.get("author", "?")
                msg_content = ev.data.get("content", "")
                channel = ev.data.get("channel_name", "?")
                channel_id = ev.data.get("channel_id", "?")
                message_id = ev.data.get("message_id", "?")
                line = f"[{ts}] #{channel}(id:{channel_id}) {author}: {msg_content} (msg_id:{message_id})"

                # Append text file contents inline
                for tf in ev.data.get("text_files", []):
                    line += f"\n--- fichier: {tf['filename']} ---\n{tf['content']}\n---"

                text_lines.append(line)

                for img in ev.data.get("images_b64", []):
                    # Flush text before inserting image
                    if text_lines:
                        content_parts.append({"type": "text", "text": "\n".join(text_lines)})
                        text_lines = []
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{img['mime']};base64,{img['base64']}"},
                    })

            case "reaction_add":
                user = ev.data.get("user", "?")
                emoji = ev.data.get("emoji", "?")
                channel = ev.data.get("channel_name", "?")
                text_lines.append(f"[{ts}] #{channel} {user} a reagi avec {emoji}")
            case _:
                text_lines.append(f"[{ts}] {ev.kind}: {json.dumps(ev.data, ensure_ascii=False)}")

    # Flush remaining text
    if text_lines:
        content_parts.append({"type": "text", "text": "\n".join(text_lines)})

    return content_parts


_llm_was_down = False

async def check_llm_available() -> bool:
    """Check if the vLLM server is reachable."""
    global _llm_was_down
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            resp = await client.get(f"{config.LLM_BASE_URL}/models")
            if resp.status_code == 200:
                if _llm_was_down:
                    log.info("LLM server is back online at %s", config.LLM_BASE_URL)
                    _llm_was_down = False
                return True
    except Exception:
        pass
    if not _llm_was_down:
        log.warning("LLM server unreachable at %s", config.LLM_BASE_URL)
        _llm_was_down = True
    return False


async def run_agent_tick(
    bot: discord.Client,
    session: Session,
    llm_client: AsyncOpenAI,
) -> None:
    """Process one agent tick for a session."""
    events = session.drain_events()
    if not events:
        return

    log.info("Session %s processing %d events", session.key, len(events))

    event_parts = _build_events_content(events)
    header = {"type": "text", "text": "Nouveaux evenements:"}
    user_content = [header] + event_parts

    # Simplify to plain string when no images (lighter history)
    has_images = any(p.get("type") == "image_url" for p in user_content)
    if not has_images:
        flat = "\n".join(p["text"] for p in user_content)
        session.conversation_history.append({"role": "user", "content": flat})
    else:
        session.conversation_history.append({"role": "user", "content": user_content})

    # Trim history
    if len(session.conversation_history) > 100:
        session.conversation_history = session.conversation_history[-50:]

    # LLM tool loop (max 5 rounds)
    max_rounds = 5
    for round_num in range(max_rounds):
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _build_system_prompt(session)},
            *session.conversation_history,
        ]

        try:
            response = await llm_client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                max_tokens=config.LLM_MAX_TOKENS,
            )
        except Exception:
            log.exception("LLM call failed for session %s (round %d)", session.key, round_num)
            if round_num == 0:
                session.events = events + session.events
                session.conversation_history.pop()
            return

        choice = response.choices[0]
        assistant_msg = choice.message

        history_entry: dict[str, Any] = {"role": "assistant"}
        if assistant_msg.content:
            history_entry["content"] = assistant_msg.content
        if assistant_msg.tool_calls:
            history_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in assistant_msg.tool_calls
            ]
        session.conversation_history.append(history_entry)

        if not assistant_msg.tool_calls:
            if assistant_msg.content:
                log.info("Session %s LLM said (no tool): %s", session.key, assistant_msg.content[:100])
            else:
                log.warning("Session %s LLM returned empty response (round %d, finish_reason=%s)", session.key, round_num, choice.finish_reason)
            break

        for tc in assistant_msg.tool_calls:
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            log.info("Session %s calling tool %s(%s)", session.key, fn_name, fn_args)
            result = await execute_tool(bot, fn_name, fn_args)
            log.info("Session %s tool %s result: %s", session.key, fn_name, result[:500])

            session.conversation_history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

        # do_nothing doesn't need a follow-up LLM call
        tool_names = {tc.function.name for tc in assistant_msg.tool_calls}
        if tool_names == {"do_nothing"}:
            break

    session.save()
