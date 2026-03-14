"""Test compatibility between obabot and aiogram."""

import pytest
from obabot import create_bot
from obabot.filters import Command, F
from obabot.fsm import State, StatesGroup, FSMContext


class TestAPICompatibility:
    """Test that obabot API matches aiogram API."""
    
    def test_import_compatibility(self):
        """Test that imports work the same way."""
        # obabot imports
        from obabot import create_bot
        from obabot.filters import Command, F
        from obabot.fsm import State, StatesGroup, FSMContext
        
        # Should work without errors
        assert create_bot is not None
        assert Command is not None
        assert F is not None
        assert State is not None
        assert StatesGroup is not None
        assert FSMContext is not None
    
    def test_decorator_compatibility(self, obabot_telegram_bot, aiogram_bot):
        """Test that decorators work the same way."""
        _, obabot_dp, obabot_router = obabot_telegram_bot
        _, aiogram_dp, aiogram_router = aiogram_bot
        
        # Both should support router.message()
        @obabot_router.message(Command("test"))
        async def obabot_handler(message):
            pass
        
        @aiogram_router.message(Command("test"))
        async def aiogram_handler(message):
            pass
        
        # Both should support dp.message()
        @obabot_dp.message(Command("test2"))
        async def obabot_dp_handler(message):
            pass
        
        @aiogram_dp.message(Command("test2"))
        async def aiogram_dp_handler(message):
            pass
        
        assert all(callable(h) for h in [
            obabot_handler, aiogram_handler,
            obabot_dp_handler, aiogram_dp_handler
        ])
    
    def test_fsm_compatibility(self, obabot_telegram_bot):
        """Test FSM compatibility."""
        _, _, router = obabot_telegram_bot
        
        class TestForm(StatesGroup):
            name = State()
            age = State()
        
        @router.message(Command("start"))
        async def start(message, state: FSMContext):
            await state.set_state(TestForm.name)
        
        @router.message(TestForm.name)
        async def process_name(message, state: FSMContext):
            await state.update_data(name=message.text)
            await state.set_state(TestForm.age)
        
        # Should work without errors
        assert callable(start)
        assert callable(process_name)


class TestMethodSignatures:
    """Test that method signatures match aiogram."""
    
    @pytest.mark.asyncio
    async def test_send_message_signature(self, obabot_telegram_bot, aiogram_bot):
        """Test that send_message has compatible signature."""
        obabot_bot, _, _ = obabot_telegram_bot
        aiogram_bot_obj, _, _ = aiogram_bot
        
        # Both should have send_message with chat_id and text
        import inspect
        
        obabot_sig = inspect.signature(obabot_bot.send_message)
        aiogram_sig = inspect.signature(aiogram_bot_obj.send_message)
        
        # Both should have chat_id and text parameters
        assert 'chat_id' in obabot_sig.parameters
        assert 'text' in obabot_sig.parameters
        assert 'chat_id' in aiogram_sig.parameters
        assert 'text' in aiogram_sig.parameters

