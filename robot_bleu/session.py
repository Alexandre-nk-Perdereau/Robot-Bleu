"""Session management -- one session per guild (server-wide) or per channel."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import discord

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"


class SessionMode(Enum):
    SERVER = "server"
    CHANNEL = "channel"


@dataclass
class Event:
    """A Discord event captured for the agent to process."""

    timestamp: float
    kind: str  # "message", "reaction_add", "reaction_remove", "member_join", ...
    data: dict[str, Any] = field(default_factory=dict)


class IdMapper:
    """Maps large Discord IDs to small sequential integers."""

    def __init__(self) -> None:
        self._to_short: dict[int, int] = {}
        self._to_real: dict[int, int] = {}
        self._next: int = 1

    def to_short(self, real_id: int) -> int:
        if real_id not in self._to_short:
            short = self._next
            self._next += 1
            self._to_short[real_id] = short
            self._to_real[short] = real_id
        return self._to_short[real_id]

    def to_real(self, short_id: int) -> int | None:
        return self._to_real.get(short_id)


@dataclass
class Session:
    """An active agent session bound to a guild or channel."""

    mode: SessionMode
    guild_id: int
    channel_id: int | None  # None if server-wide
    persona: str = ""
    bot_display_name: str = ""
    guild_name: str = ""
    channel_names: list[str] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    enabled: bool = False
    channel_ids: IdMapper = field(default_factory=IdMapper)
    message_ids: IdMapper = field(default_factory=IdMapper)

    @property
    def key(self) -> str:
        if self.mode == SessionMode.SERVER:
            return f"guild:{self.guild_id}"
        return f"channel:{self.guild_id}:{self.channel_id}"

    def push_event(self, kind: str, **data: Any) -> None:
        self.events.append(Event(timestamp=time.time(), kind=kind, data=data))

    def drain_events(self) -> list[Event]:
        """Return and clear pending events."""
        events = self.events
        self.events = []
        return events

    # -- Persistence --

    def _file_path(self) -> Path:
        safe_key = self.key.replace(":", "_")
        return DATA_DIR / f"{safe_key}.json"

    def save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "mode": self.mode.value,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "persona": self.persona,
            "bot_display_name": self.bot_display_name,
            "guild_name": self.guild_name,
            "channel_names": self.channel_names,
            "enabled": self.enabled,
            "conversation_history": self.conversation_history,
        }
        self._file_path().write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def load(cls, path: Path) -> Session:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            mode=SessionMode(data["mode"]),
            guild_id=data["guild_id"],
            channel_id=data["channel_id"],
            persona=data["persona"],
            bot_display_name=data.get("bot_display_name", ""),
            guild_name=data["guild_name"],
            channel_names=data.get("channel_names", []),
            enabled=data.get("enabled", True),
            conversation_history=data.get("conversation_history", []),
        )

    def delete_data(self) -> None:
        path = self._file_path()
        if path.exists():
            path.unlink()


class SessionManager:
    """Registry of all active sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._load_all()

    def _load_all(self) -> None:
        if not DATA_DIR.exists():
            return
        for path in DATA_DIR.glob("*.json"):
            try:
                session = Session.load(path)
                if session.enabled:
                    self._sessions[session.key] = session
                    log.info("Restored session: %s", session.key)
            except Exception:
                log.warning("Failed to load session from %s", path, exc_info=True)

    def save_all(self) -> None:
        for session in self._sessions.values():
            session.save()

    def get(self, guild_id: int, channel_id: int | None = None) -> Session | None:
        if channel_id is not None:
            key = f"channel:{guild_id}:{channel_id}"
            if key in self._sessions:
                return self._sessions[key]
        key = f"guild:{guild_id}"
        result = self._sessions.get(key)
        log.debug(
            "get(guild=%s, channel=%s) -> %s (keys: %s)",
            guild_id,
            channel_id,
            result.key if result else None,
            list(self._sessions.keys()),
        )
        return result

    def activate(
        self,
        guild: discord.Guild,
        mode: SessionMode,
        persona: str,
        channel_id: int | None = None,
    ) -> Session:
        session = Session(
            mode=mode,
            guild_id=guild.id,
            channel_id=channel_id,
            persona=persona,
            bot_display_name=guild.me.display_name if guild.me else "",
            guild_name=guild.name,
            channel_names=[ch.name for ch in guild.text_channels],
            enabled=True,
        )
        self._sessions[session.key] = session
        session.save()
        return session

    def deactivate(self, guild_id: int, channel_id: int | None = None) -> bool:
        session = self.get(guild_id, channel_id)
        if session:
            session.enabled = False
            session.save()
            del self._sessions[session.key]
            return True
        return False

    @property
    def active_sessions(self) -> list[Session]:
        return [s for s in self._sessions.values() if s.enabled]
