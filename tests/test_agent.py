from __future__ import annotations

import time
from unittest.mock import patch

from robot_bleu.agent import _build_events_content, _build_extra_body, _build_system_prompt
from robot_bleu.session import Event, Session, SessionMode


def _session(**overrides) -> Session:
    defaults = dict(
        mode=SessionMode.SERVER,
        guild_id=1,
        channel_id=None,
        persona="Tu es un robot cool.",
        bot_display_name="Bleu",
        guild_name="TestServer",
    )
    defaults.update(overrides)
    return Session(**defaults)


def _event(kind: str, **data) -> Event:
    return Event(timestamp=time.time(), kind=kind, data=data)


class TestBuildSystemPrompt:
    def test_contains_persona(self):
        s = _session(persona="Je suis sympa.")
        prompt = _build_system_prompt(s)
        assert "Je suis sympa." in prompt

    def test_contains_bot_name(self):
        s = _session(bot_display_name="Bleu")
        prompt = _build_system_prompt(s)
        assert "Bleu" in prompt

    def test_contains_guild_name(self):
        s = _session(guild_name="Mon Serveur")
        prompt = _build_system_prompt(s)
        assert "Mon Serveur" in prompt

    def test_no_bot_name(self):
        s = _session(bot_display_name="")
        prompt = _build_system_prompt(s)
        assert "Ton nom est" not in prompt


class TestBuildEventsContent:
    def test_empty_events(self):
        s = _session()
        parts = _build_events_content([], s)
        assert len(parts) == 1
        assert "Aucun" in parts[0]["text"]

    def test_message_event(self):
        s = _session()
        ev = _event(
            "message",
            author="Alice",
            content="Salut!",
            channel_name="general",
            channel_id=100,
            message_id=200,
        )
        parts = _build_events_content([ev], s)
        text = parts[0]["text"]
        assert "Alice" in text
        assert "Salut!" in text
        assert "#general" in text

    def test_reaction_event(self):
        s = _session()
        ev = _event(
            "reaction_add",
            user="Bob",
            emoji="🔥",
            channel_name="general",
            channel_id=100,
            message_id=200,
        )
        parts = _build_events_content([ev], s)
        text = parts[0]["text"]
        assert "Bob" in text
        assert "🔥" in text
        assert "reagi" in text

    def test_message_with_image(self):
        s = _session()
        ev = _event(
            "message",
            author="Carol",
            content="Regarde",
            channel_name="photos",
            channel_id=100,
            message_id=200,
            images_b64=[{"mime": "image/png", "base64": "AAAA"}],
        )
        parts = _build_events_content([ev], s)
        assert any(p["type"] == "text" for p in parts)
        assert any(p["type"] == "image_url" for p in parts)
        img_part = next(p for p in parts if p["type"] == "image_url")
        assert "data:image/png;base64,AAAA" in img_part["image_url"]["url"]

    def test_message_with_text_file(self):
        s = _session()
        ev = _event(
            "message",
            author="Dave",
            content="Mon code",
            channel_name="dev",
            channel_id=100,
            message_id=200,
            text_files=[{"filename": "main.py", "content": "print('hi')"}],
        )
        parts = _build_events_content([ev], s)
        text = parts[0]["text"]
        assert "main.py" in text
        assert "print('hi')" in text

    def test_unknown_event_kind(self):
        s = _session()
        ev = _event("member_join", username="NewUser", channel_id=100)
        parts = _build_events_content([ev], s)
        text = parts[0]["text"]
        assert "member_join" in text
        assert "NewUser" in text

    def test_id_mapping_applied(self):
        s = _session()
        ev = _event(
            "message",
            author="X",
            content="Y",
            channel_name="c",
            channel_id=999_000_111,
            message_id=888_000_222,
        )
        _build_events_content([ev], s)
        assert s.channel_ids.to_real(s.channel_ids.to_short(999_000_111)) == 999_000_111
        assert s.message_ids.to_real(s.message_ids.to_short(888_000_222)) == 888_000_222


class TestBuildExtraBody:
    def test_vllm_with_thinking(self):
        with patch("robot_bleu.agent.config") as cfg:
            cfg.LLM_BACKEND = "vllm"
            cfg.LLM_MAX_THINKING_TOKENS = 1024
            result = _build_extra_body()

        assert result["chat_template_kwargs"]["enable_thinking"] is True
        assert result["thinking_budget"] == 1024

    def test_vllm_without_thinking(self):
        with patch("robot_bleu.agent.config") as cfg:
            cfg.LLM_BACKEND = "vllm"
            cfg.LLM_MAX_THINKING_TOKENS = 0
            result = _build_extra_body()

        assert result["chat_template_kwargs"]["enable_thinking"] is False
        assert "thinking_budget" not in result

    def test_ollama_with_thinking(self):
        with patch("robot_bleu.agent.config") as cfg:
            cfg.LLM_BACKEND = "ollama"
            cfg.LLM_MAX_THINKING_TOKENS = 512
            result = _build_extra_body()

        assert result == {"think": True}

    def test_ollama_without_thinking(self):
        with patch("robot_bleu.agent.config") as cfg:
            cfg.LLM_BACKEND = "ollama"
            cfg.LLM_MAX_THINKING_TOKENS = 0
            result = _build_extra_body()

        assert result is None

    def test_unknown_backend(self):
        with patch("robot_bleu.agent.config") as cfg:
            cfg.LLM_BACKEND = "something_else"
            cfg.LLM_MAX_THINKING_TOKENS = 100
            result = _build_extra_body()

        assert result is None
