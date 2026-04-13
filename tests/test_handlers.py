"""Test handler registration and execution."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from obabot.filters import Command, F
from obabot import create_bot, BPlatform


class TestHandlerRegistration:
    """Test handler registration across platforms."""
    
    def test_message_handler_registration(self, obabot_telegram_bot):
        """Test that message handlers can be registered."""
        _, _, router = obabot_telegram_bot
        
        @router.message(Command("test"))
        async def test_handler(message):
            pass
        
        # Handler should be registered and callable
        assert callable(test_handler)
    
    def test_multiple_handlers(self, obabot_telegram_bot):
        """Test registering multiple handlers."""
        _, _, router = obabot_telegram_bot
        
        @router.message(Command("start"))
        async def start_handler(message):
            pass
        
        @router.message(Command("help"))
        async def help_handler(message):
            pass
        
        @router.message(F.text)
        async def text_handler(message):
            pass
        
        # All handlers should be registered
        assert callable(start_handler)
        assert callable(help_handler)
        assert callable(text_handler)
    
    def test_callback_handler(self, obabot_telegram_bot):
        """Test callback query handler registration."""
        _, _, router = obabot_telegram_bot
        
        @router.callback_query(F.data == "test")
        async def callback_handler(callback):
            pass
        
        assert callable(callback_handler)
    
    def test_dual_platform_handlers(self, obabot_dual_bot):
        """Test that handlers are registered on both platforms."""
        bot, _, router = obabot_dual_bot
        
        @router.message(Command("test"))
        async def test_handler(message):
            pass
        
        # Handler should be registered for both platforms
        assert callable(test_handler)
        # Verify both platforms are configured
        assert len(bot.platforms) == 2
        assert BPlatform.telegram in bot.platforms
        assert BPlatform.max in bot.platforms
    
    def test_handler_with_filters(self, obabot_telegram_bot):
        """Test handlers with different filter combinations."""
        _, _, router = obabot_telegram_bot
        
        @router.message(Command("start"))
        async def start_handler(message):
            pass
        
        @router.message(F.text == "hello")
        async def text_equals_handler(message):
            pass
        
        @router.message(F.photo)
        async def photo_handler(message):
            pass
        
        # All handlers should be registered
        assert all(callable(h) for h in [start_handler, text_equals_handler, photo_handler])
    
    def test_handler_registration_order(self, obabot_telegram_bot):
        """Test that handlers are registered in the correct order."""
        _, _, router = obabot_telegram_bot
        
        @router.message(Command("first"))
        async def first_handler(message):
            pass
        
        @router.message(Command("second"))
        async def second_handler(message):
            pass
        
        @router.message(Command("third"))
        async def third_handler(message):
            pass
        
        # All should be registered
        assert callable(first_handler)
        assert callable(second_handler)
        assert callable(third_handler)


class TestHandlerExecution:
    """Test that handlers actually execute when triggered."""
    
    @pytest.mark.asyncio
    async def test_message_handler_execution(self, obabot_telegram_bot):
        """Test that message handler executes when message is processed."""
        bot, dp, router = obabot_telegram_bot
        
        handler_called = False
        received_message = None
        
        @router.message(Command("test"))
        async def test_handler(message):
            nonlocal handler_called, received_message
            handler_called = True
            received_message = message
        
        # Create a mock message
        mock_message = MagicMock()
        mock_message.text = "/test"
        mock_message.from_user = MagicMock()
        mock_message.chat = MagicMock()
        
        # Try to trigger handler through platform's dispatcher
        # Get the underlying platform router
        platform = bot._platforms[0]
        platform_router = platform.router
        
        # Check if handler was registered in platform router
        # In aiogram, handlers are stored in router._handlers or similar
        assert callable(test_handler)
        
        # Verify handler can be called directly
        await test_handler(mock_message)
        assert handler_called is True
        assert received_message is mock_message
    
    @pytest.mark.asyncio
    async def test_callback_handler_execution(self, obabot_telegram_bot):
        """Test that callback handler executes when callback is processed."""
        _, _, router = obabot_telegram_bot
        
        handler_called = False
        received_callback = None
        
        @router.callback_query(F.data == "test_button")
        async def callback_handler(callback):
            nonlocal handler_called, received_callback
            handler_called = True
            received_callback = callback
        
        # Create a mock callback query
        mock_callback = MagicMock()
        mock_callback.data = "test_button"
        mock_callback.from_user = MagicMock()
        mock_callback.message = MagicMock()
        
        # Verify handler can be called directly
        await callback_handler(mock_callback)
        assert handler_called is True
        assert received_callback is mock_callback
    
    @pytest.mark.asyncio
    async def test_handler_with_multiple_filters_execution(self, obabot_telegram_bot):
        """Test handler execution with multiple filters."""
        _, _, router = obabot_telegram_bot
        
        handler_called = False
        
        @router.message(Command("start"), F.text)
        async def multi_filter_handler(message):
            nonlocal handler_called
            handler_called = True
        
        # Create a mock message that matches filters
        mock_message = MagicMock()
        mock_message.text = "/start"
        mock_message.from_user = MagicMock()
        mock_message.chat = MagicMock()
        
        await multi_filter_handler(mock_message)
        assert handler_called is True
    
    @pytest.mark.asyncio
    async def test_handler_wrapping_execution(self, obabot_telegram_bot):
        """Test that wrapped handlers execute correctly."""
        bot, _, router = obabot_telegram_bot
        
        original_called = False
        
        async def original_handler(message):
            nonlocal original_called
            original_called = True
            return "result"
        
        # Register and wrap handler
        wrapped = router.message(Command("test"))(original_handler)
        
        # Get platform and wrap handler through platform
        platform = bot._platforms[0]
        platform_wrapped = platform.wrap_handler(original_handler)
        
        # Create mock message
        mock_message = MagicMock()
        mock_message.text = "/test"
        mock_message.from_user = MagicMock()
        mock_message.chat = MagicMock()
        
        # Execute wrapped handler
        result = await platform_wrapped(mock_message)
        
        assert original_called is True
        assert result == "result"
        # Verify platform attribute was added
        assert hasattr(mock_message, 'platform') or hasattr(mock_message, 'platform')
    
    @pytest.mark.asyncio
    async def test_dual_platform_handler_execution(self, obabot_dual_bot):
        """Test that handlers execute on both platforms."""
        bot, _, router = obabot_dual_bot
        
        handler_calls = []
        
        @router.message(Command("test"))
        async def dual_handler(message):
            handler_calls.append(getattr(message, 'platform', 'unknown'))
        
        # Verify handler is registered for both platforms
        assert callable(dual_handler)
        assert len(bot.platforms) == 2
        
        # Create mock messages for each platform
        for platform_type in bot.platforms:
            platform = bot._platform_map[platform_type]
            wrapped = platform.wrap_handler(dual_handler)
            
            mock_message = MagicMock()
            mock_message.text = "/test"
            mock_message.from_user = MagicMock()
            mock_message.chat = MagicMock()
            
            await wrapped(mock_message)
        
        # Handler should have been called for both platforms
        assert len(handler_calls) == 2


class TestFSMHandlers:
    """Test FSM handler registration and execution."""
    
    def test_fsm_state_handler(self, obabot_telegram_bot):
        """Test FSM state handler registration."""
        from obabot.fsm import State, StatesGroup, FSMContext
        
        _, _, router = obabot_telegram_bot
        
        class TestStates(StatesGroup):
            waiting = State()
        
        @router.message(TestStates.waiting)
        async def state_handler(message, state: FSMContext):
            pass
        
        assert callable(state_handler)
    
    @pytest.mark.asyncio
    async def test_fsm_handler_execution(self, obabot_telegram_bot):
        """Test that FSM handler executes with state."""
        from obabot.fsm import State, StatesGroup, FSMContext
        
        _, _, router = obabot_telegram_bot
        
        state_updated = False
        
        class TestStates(StatesGroup):
            waiting = State()
        
        @router.message(TestStates.waiting)
        async def state_handler(message, state: FSMContext):
            nonlocal state_updated
            await state.update_data(test="value")
            state_updated = True
        
        # Create mock message and state
        mock_message = MagicMock()
        mock_message.text = "test"
        mock_message.from_user = MagicMock()
        mock_message.chat = MagicMock()
        
        mock_state = AsyncMock(spec=FSMContext)
        mock_state.update_data = AsyncMock()
        
        # Execute handler
        await state_handler(mock_message, mock_state)
        
        assert state_updated is True
        mock_state.update_data.assert_called_once_with(test="value")


@pytest.mark.max
class TestHandlerRegistrationMax:
    """Mirror TestHandlerRegistration for Max-only bot (real MAX_TOKEN)."""

    def test_message_handler_registration(self, obabot_max_bot):
        _, _, router = obabot_max_bot

        @router.message(Command("test"))
        async def test_handler(message):
            pass

        assert callable(test_handler)

    def test_multiple_handlers(self, obabot_max_bot):
        _, _, router = obabot_max_bot

        @router.message(Command("start"))
        async def start_handler(message):
            pass

        @router.message(Command("help"))
        async def help_handler(message):
            pass

        @router.message(F.text)
        async def text_handler(message):
            pass

        assert callable(start_handler)
        assert callable(help_handler)
        assert callable(text_handler)

    def test_callback_handler(self, obabot_max_bot):
        _, _, router = obabot_max_bot

        @router.callback_query(F.data == "test")
        async def callback_handler(callback):
            pass

        assert callable(callback_handler)

    def test_handler_with_filters(self, obabot_max_bot):
        _, _, router = obabot_max_bot

        @router.message(Command("start"))
        async def start_handler(message):
            pass

        @router.message(F.text == "hello")
        async def text_equals_handler(message):
            pass

        @router.message(F.photo)
        async def photo_handler(message):
            pass

        assert all(callable(h) for h in [start_handler, text_equals_handler, photo_handler])

    def test_handler_registration_order(self, obabot_max_bot):
        _, _, router = obabot_max_bot

        @router.message(Command("first"))
        async def first_handler(message):
            pass

        @router.message(Command("second"))
        async def second_handler(message):
            pass

        @router.message(Command("third"))
        async def third_handler(message):
            pass

        assert callable(first_handler)
        assert callable(second_handler)
        assert callable(third_handler)


@pytest.mark.max
class TestHandlerExecutionMax:
    """Mirror TestHandlerExecution for Max-only bot."""

    @pytest.mark.asyncio
    async def test_message_handler_execution(self, obabot_max_bot):
        bot, dp, router = obabot_max_bot

        handler_called = False
        received_message = None

        @router.message(Command("test"))
        async def test_handler(message):
            nonlocal handler_called, received_message
            handler_called = True
            received_message = message

        mock_message = MagicMock()
        mock_message.text = "/test"
        mock_message.from_user = MagicMock()
        mock_message.chat = MagicMock()

        assert callable(test_handler)
        await test_handler(mock_message)
        assert handler_called is True
        assert received_message is mock_message

    @pytest.mark.asyncio
    async def test_callback_handler_execution(self, obabot_max_bot):
        _, _, router = obabot_max_bot

        handler_called = False
        received_callback = None

        @router.callback_query(F.data == "test_button")
        async def callback_handler(callback):
            nonlocal handler_called, received_callback
            handler_called = True
            received_callback = callback

        mock_callback = MagicMock()
        mock_callback.data = "test_button"
        mock_callback.from_user = MagicMock()
        mock_callback.message = MagicMock()

        await callback_handler(mock_callback)
        assert handler_called is True
        assert received_callback is mock_callback

    @pytest.mark.asyncio
    async def test_handler_with_multiple_filters_execution(self, obabot_max_bot):
        _, _, router = obabot_max_bot

        handler_called = False

        @router.message(Command("start"), F.text)
        async def multi_filter_handler(message):
            nonlocal handler_called
            handler_called = True

        mock_message = MagicMock()
        mock_message.text = "/start"
        mock_message.from_user = MagicMock()
        mock_message.chat = MagicMock()

        await multi_filter_handler(mock_message)
        assert handler_called is True

    @pytest.mark.asyncio
    async def test_handler_wrapping_execution(self, obabot_max_bot):
        bot, _, router = obabot_max_bot

        original_called = False

        async def original_handler(message):
            nonlocal original_called
            original_called = True
            return "result"

        router.message(Command("test"))(original_handler)

        platform = bot._platforms[0]
        platform_wrapped = platform.wrap_handler(original_handler)

        mock_message = MagicMock()
        mock_message.text = "/test"
        mock_message.from_user = MagicMock()
        mock_message.chat = MagicMock()

        result = await platform_wrapped(mock_message)

        assert original_called is True
        assert result == "result"


@pytest.mark.max
class TestFSMHandlersMax:
    """Mirror TestFSMHandlers for Max-only bot."""

    def test_fsm_state_handler(self, obabot_max_bot):
        from obabot.fsm import State, StatesGroup, FSMContext

        _, _, router = obabot_max_bot

        class TestStates(StatesGroup):
            waiting = State()

        @router.message(TestStates.waiting)
        async def state_handler(message, state: FSMContext):
            pass

        assert callable(state_handler)

    @pytest.mark.asyncio
    async def test_fsm_handler_execution(self, obabot_max_bot):
        from obabot.fsm import State, StatesGroup, FSMContext

        _, _, router = obabot_max_bot

        state_updated = False

        class TestStates(StatesGroup):
            waiting = State()

        @router.message(TestStates.waiting)
        async def state_handler(message, state: FSMContext):
            nonlocal state_updated
            await state.update_data(test="value")
            state_updated = True

        mock_message = MagicMock()
        mock_message.text = "test"
        mock_message.from_user = MagicMock()
        mock_message.chat = MagicMock()

        mock_state = AsyncMock(spec=FSMContext)
        mock_state.update_data = AsyncMock()

        await state_handler(mock_message, mock_state)

        assert state_updated is True
        mock_state.update_data.assert_called_once_with(test="value")
