from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from robot_bleu.session import IdMapper, Session, SessionManager, SessionMode


class TestIdMapper:
    def test_sequential_assignment(self):
        m = IdMapper()
        assert m.to_short(999_000_111) == 1
        assert m.to_short(999_000_222) == 2
        assert m.to_short(999_000_333) == 3

    def test_same_id_returns_same_short(self):
        m = IdMapper()
        first = m.to_short(42)
        second = m.to_short(42)
        assert first == second == 1

    def test_to_real_roundtrip(self):
        m = IdMapper()
        real_id = 123_456_789
        short = m.to_short(real_id)
        assert m.to_real(short) == real_id

    def test_to_real_unknown(self):
        m = IdMapper()
        assert m.to_real(999) is None

    def test_multiple_roundtrips(self):
        m = IdMapper()
        ids = [111, 222, 333, 444]
        shorts = [m.to_short(i) for i in ids]
        for real, short in zip(ids, shorts):
            assert m.to_real(short) == real


class TestSessionKey:
    def test_server_mode_key(self):
        s = Session(mode=SessionMode.SERVER, guild_id=100, channel_id=None)
        assert s.key == "guild:100"

    def test_channel_mode_key(self):
        s = Session(mode=SessionMode.CHANNEL, guild_id=100, channel_id=200)
        assert s.key == "channel:100:200"


class TestSessionEvents:
    def test_push_and_drain(self):
        s = Session(mode=SessionMode.SERVER, guild_id=1, channel_id=None)
        s.push_event("message", content="hello")
        s.push_event("reaction_add", emoji="👍")
        events = s.drain_events()

        assert len(events) == 2
        assert events[0].kind == "message"
        assert events[0].data["content"] == "hello"
        assert events[1].kind == "reaction_add"

    def test_drain_clears(self):
        s = Session(mode=SessionMode.SERVER, guild_id=1, channel_id=None)
        s.push_event("message", content="x")
        s.drain_events()
        assert s.drain_events() == []


class TestSessionPersistence:
    def test_save_load_roundtrip(self, tmp_path: Path):
        s = Session(
            mode=SessionMode.CHANNEL,
            guild_id=100,
            channel_id=200,
            persona="test persona",
            bot_display_name="Bleu",
            guild_name="My Server",
            channel_names=["general", "bot"],
            enabled=True,
            conversation_history=[{"role": "user", "content": "hi"}],
        )
        with patch("robot_bleu.session.DATA_DIR", tmp_path):
            s.save()
            loaded = Session.load(s._file_path())

        assert loaded.mode == SessionMode.CHANNEL
        assert loaded.guild_id == 100
        assert loaded.channel_id == 200
        assert loaded.persona == "test persona"
        assert loaded.bot_display_name == "Bleu"
        assert loaded.guild_name == "My Server"
        assert loaded.channel_names == ["general", "bot"]
        assert loaded.enabled is True
        assert loaded.conversation_history == [{"role": "user", "content": "hi"}]

    def test_load_missing_optional_fields(self, tmp_path: Path):
        data = {
            "mode": "server",
            "guild_id": 1,
            "channel_id": None,
            "persona": "",
            "guild_name": "G",
        }
        path = tmp_path / "guild_1.json"
        path.write_text(json.dumps(data))

        loaded = Session.load(path)
        assert loaded.bot_display_name == ""
        assert loaded.channel_names == []
        assert loaded.enabled is True
        assert loaded.conversation_history == []


class TestSessionManagerGet:
    def _make_manager(self, tmp_path: Path) -> SessionManager:
        with patch("robot_bleu.session.DATA_DIR", tmp_path):
            return SessionManager()

    def test_get_returns_none_when_empty(self, tmp_path: Path):
        mgr = self._make_manager(tmp_path)
        assert mgr.get(guild_id=1, channel_id=10) is None

    def test_get_guild_session(self, tmp_path: Path):
        mgr = self._make_manager(tmp_path)
        s = Session(mode=SessionMode.SERVER, guild_id=1, channel_id=None, enabled=True)
        mgr._sessions[s.key] = s

        assert mgr.get(guild_id=1) is s

    def test_get_falls_back_to_guild(self, tmp_path: Path):
        mgr = self._make_manager(tmp_path)
        s = Session(mode=SessionMode.SERVER, guild_id=1, channel_id=None, enabled=True)
        mgr._sessions[s.key] = s

        assert mgr.get(guild_id=1, channel_id=99) is s

    def test_get_prefers_channel_session(self, tmp_path: Path):
        mgr = self._make_manager(tmp_path)
        guild_s = Session(
            mode=SessionMode.SERVER, guild_id=1, channel_id=None, enabled=True
        )
        chan_s = Session(
            mode=SessionMode.CHANNEL, guild_id=1, channel_id=42, enabled=True
        )
        mgr._sessions[guild_s.key] = guild_s
        mgr._sessions[chan_s.key] = chan_s

        assert mgr.get(guild_id=1, channel_id=42) is chan_s
        assert mgr.get(guild_id=1, channel_id=99) is guild_s
