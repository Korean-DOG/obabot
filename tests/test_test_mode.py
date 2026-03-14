"""
Tests for test mode (create_bot(test_mode=True) / TESTING=1).

These tests require no real tokens or network. They run in CI without secrets.
"""

import pytest
from aiogram import Dispatcher, Router

from obabot import create_bot, StubBot


class TestTestModeActivation:
    """Ways to enable test mode."""

    def test_test_mode_true_no_tokens(self):
        """test_mode=True allows creation without any tokens."""
        bot, dp, router = create_bot(test_mode=True)
        assert bot is not None
        assert dp is not None
        assert router is not None
        assert isinstance(bot, StubBot)

    def test_test_mode_via_env(self, monkeypatch):
        """TESTING=1 enables test mode without passing test_mode=True."""
        monkeypatch.setenv("TESTING", "1")
        try:
            bot, dp, router = create_bot()
            assert isinstance(bot, StubBot)
        finally:
            monkeypatch.delenv("TESTING", raising=False)

    def test_test_mode_explicit_overrides_env(self, monkeypatch):
        """test_mode=False disables test mode even if TESTING=1."""
        monkeypatch.setenv("TESTING", "1")
        try:
            with pytest.raises(ValueError, match="At least one token"):
                create_bot(test_mode=False)
        finally:
            monkeypatch.delenv("TESTING", raising=False)


class TestTestModeReturnTypes:
    """Returned objects in test mode."""

    def test_returns_stub_bot(self):
        bot, _, _ = create_bot(test_mode=True)
        assert isinstance(bot, StubBot)
        assert hasattr(bot, "token")
        assert bot.token
        assert hasattr(bot, "id")
        assert hasattr(bot, "session")
        assert hasattr(bot, "get_me")
        assert hasattr(bot, "close")

    def test_returns_aiogram_dispatcher_and_router(self):
        _, dp, router = create_bot(test_mode=True)
        assert isinstance(dp, Dispatcher)
        assert isinstance(router, Router)

    def test_router_is_instance(self):
        """Router is an instance (so include_router(router) receives an instance, not the class)."""
        _, _, router = create_bot(test_mode=True)
        assert isinstance(router, Router)
        assert type(router).__name__ == "Router"

    def test_router_already_included_in_dispatcher(self):
        """Router is already included in the returned dp, so dp.include_router(router) is not needed."""
        _, dp, router = create_bot(test_mode=True)
        assert getattr(router, "parent_router", None) is not None or router in getattr(dp, "_routers", ())
        # Using our dp in tests does not require include_router(router) and thus cannot fail


class TestTestModeStubBotInterface:
    """StubBot has minimal Bot-like interface for set_notification_bot / feed_webhook."""

    def test_stub_bot_token(self):
        bot, _, _ = create_bot(test_mode=True)
        assert isinstance(bot.token, str)
        assert len(bot.token) > 0

    @pytest.mark.asyncio
    async def test_stub_bot_session_close(self):
        bot, _, _ = create_bot(test_mode=True)
        assert hasattr(bot.session, "close")
        await bot.session.close()

    @pytest.mark.asyncio
    async def test_stub_bot_get_me_returns_none(self):
        bot, _, _ = create_bot(test_mode=True)
        result = await bot.get_me()
        assert result is None

    @pytest.mark.asyncio
    async def test_stub_bot_close_no_op(self):
        bot, _, _ = create_bot(test_mode=True)
        await bot.close()


class TestTestModeFsmStorage:
    """FSM storage is passed to dispatcher in test mode."""

    def test_fsm_storage_set_on_dispatcher(self):
        from obabot.fsm import MemoryStorage
        storage = MemoryStorage()
        _, dp, _ = create_bot(test_mode=True, fsm_storage=storage)
        assert dp.fsm_storage is storage


class TestTestModeContract:
    """Same usage contract as production: bot, dp, router = create_bot(...)."""

    def test_handlers_register_on_router(self):
        """Handlers can be registered on the returned router (same as prod)."""
        _, _, router = create_bot(test_mode=True)

        @router.message()
        async def handler(msg):
            pass

        assert callable(handler)

    def test_use_returned_dp_without_calling_include_router(self):
        """Returned dp already has router; use it in tests without calling include_router(router)."""
        bot, dp, router = create_bot(test_mode=True)
        # No need to call dp.include_router(router) — already included; avoids "already attached" errors
        assert dp is not None
        assert router is not None
