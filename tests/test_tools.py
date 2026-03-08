from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from robot_bleu.session import IdMapper
from robot_bleu.tools import _extract_text_from_html, execute_tool


@pytest.fixture
def mappers():
    ch = IdMapper()
    msg = IdMapper()
    ch.to_short(100_000)
    msg.to_short(200_000)
    return ch, msg


@pytest.fixture
def bot():
    return MagicMock()


class TestExecuteToolIdResolution:
    @pytest.mark.asyncio
    async def test_unknown_channel_id(self, bot, mappers):
        ch, msg = mappers
        result = await execute_tool(
            bot,
            "send_message",
            {"channel_id": 999, "content": "hi"},
            guild_id=1,
            channel_ids=ch,
            message_ids=msg,
        )
        assert "Unknown channel_id" in result

    @pytest.mark.asyncio
    async def test_unknown_message_id(self, bot, mappers):
        ch, msg = mappers
        result = await execute_tool(
            bot,
            "react_to_message",
            {"channel_id": 1, "message_id": 999, "emoji": "👍"},
            guild_id=1,
            channel_ids=ch,
            message_ids=msg,
        )
        assert "Unknown message_id" in result

    @pytest.mark.asyncio
    async def test_channel_id_resolved(self, bot, mappers):
        ch, msg = mappers
        channel_mock = MagicMock()
        channel_mock.name = "general"
        channel_mock.send = AsyncMock()
        bot.get_channel = MagicMock(return_value=channel_mock)

        result = await execute_tool(
            bot,
            "send_message",
            {"channel_id": 1, "content": "hello"},
            guild_id=1,
            channel_ids=ch,
            message_ids=msg,
        )
        bot.get_channel.assert_called_with(100_000)
        assert "sent" in result.lower()


class TestExecuteToolRouting:
    @pytest.mark.asyncio
    async def test_do_nothing(self, bot, mappers):
        ch, msg = mappers
        result = await execute_tool(
            bot, "do_nothing", {}, guild_id=1, channel_ids=ch, message_ids=msg
        )
        assert "nothing" in result.lower()

    @pytest.mark.asyncio
    async def test_unknown_tool(self, bot, mappers):
        ch, msg = mappers
        result = await execute_tool(
            bot, "nonexistent_tool", {}, guild_id=1, channel_ids=ch, message_ids=msg
        )
        assert "Unknown tool" in result

    @pytest.mark.asyncio
    async def test_tool_exception_caught(self, bot, mappers):
        ch, msg = mappers
        bot.get_guild = MagicMock(side_effect=RuntimeError("boom"))

        result = await execute_tool(
            bot, "list_channels", {}, guild_id=1, channel_ids=ch, message_ids=msg
        )
        assert "Error" in result


class TestReplyToMessage:
    @pytest.mark.asyncio
    async def test_reply_sends_with_reference(self, bot, mappers):
        ch, msg = mappers
        channel_mock = MagicMock()
        channel_mock.name = "general"
        channel_mock.send = AsyncMock()
        bot.get_channel = MagicMock(return_value=channel_mock)

        result = await execute_tool(
            bot,
            "reply_to_message",
            {"channel_id": 1, "message_id": 1, "content": "yo"},
            guild_id=1,
            channel_ids=ch,
            message_ids=msg,
        )
        call_kwargs = channel_mock.send.call_args
        assert call_kwargs.kwargs.get("reference") is not None
        assert "reply" in result.lower()


class TestEditMessage:
    @pytest.mark.asyncio
    async def test_edit_own_message(self, bot, mappers):
        ch, msg = mappers
        message_mock = AsyncMock()
        message_mock.author.id = 42
        bot.user.id = 42
        channel_mock = MagicMock()
        channel_mock.fetch_message = AsyncMock(return_value=message_mock)
        bot.get_channel = MagicMock(return_value=channel_mock)

        result = await execute_tool(
            bot,
            "edit_message",
            {"channel_id": 1, "message_id": 1, "content": "updated"},
            guild_id=1,
            channel_ids=ch,
            message_ids=msg,
        )
        message_mock.edit.assert_called_once_with(content="updated")
        assert "edited" in result.lower()

    @pytest.mark.asyncio
    async def test_edit_other_user_rejected(self, bot, mappers):
        ch, msg = mappers
        message_mock = AsyncMock()
        message_mock.author.id = 99
        bot.user.id = 42
        channel_mock = MagicMock()
        channel_mock.fetch_message = AsyncMock(return_value=message_mock)
        bot.get_channel = MagicMock(return_value=channel_mock)

        result = await execute_tool(
            bot,
            "edit_message",
            {"channel_id": 1, "message_id": 1, "content": "hacked"},
            guild_id=1,
            channel_ids=ch,
            message_ids=msg,
        )
        message_mock.edit.assert_not_called()
        assert "Cannot" in result


class TestDeleteMessage:
    @pytest.mark.asyncio
    async def test_delete_own_message(self, bot, mappers):
        ch, msg = mappers
        message_mock = AsyncMock()
        message_mock.author.id = 42
        bot.user.id = 42
        channel_mock = MagicMock()
        channel_mock.fetch_message = AsyncMock(return_value=message_mock)
        bot.get_channel = MagicMock(return_value=channel_mock)

        result = await execute_tool(
            bot,
            "delete_message",
            {"channel_id": 1, "message_id": 1},
            guild_id=1,
            channel_ids=ch,
            message_ids=msg,
        )
        message_mock.delete.assert_called_once()
        assert "deleted" in result.lower()

    @pytest.mark.asyncio
    async def test_delete_other_user_rejected(self, bot, mappers):
        ch, msg = mappers
        message_mock = AsyncMock()
        message_mock.author.id = 99
        bot.user.id = 42
        channel_mock = MagicMock()
        channel_mock.fetch_message = AsyncMock(return_value=message_mock)
        bot.get_channel = MagicMock(return_value=channel_mock)

        result = await execute_tool(
            bot,
            "delete_message",
            {"channel_id": 1, "message_id": 1},
            guild_id=1,
            channel_ids=ch,
            message_ids=msg,
        )
        message_mock.delete.assert_not_called()
        assert "Cannot" in result


class TestExtractTextFromHtml:
    def test_strips_tags(self):
        assert _extract_text_from_html("<p>Hello</p>") == "Hello"

    def test_removes_script_blocks(self):
        html = "<p>Hi</p><script>alert('x')</script><p>There</p>"
        result = _extract_text_from_html(html)
        assert "alert" not in result
        assert "Hi" in result and "There" in result

    def test_decodes_entities(self):
        result = _extract_text_from_html("<p>A &amp; B</p>")
        assert "A & B" in result
        assert "&amp;" not in result
