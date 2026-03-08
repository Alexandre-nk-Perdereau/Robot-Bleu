from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from robot_bleu.session import IdMapper
from robot_bleu.tools import execute_tool


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
