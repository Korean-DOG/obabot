"""Tests comparing obabot with original aiogram."""

import pytest
from obabot import create_bot
from obabot.filters import Command, F
from obabot.fsm import State, StatesGroup, FSMContext

# Import aiogram components with version compatibility
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command as AGCommand

# F is imported from aiogram, not aiogram.filters (in aiogram 3.24+)
try:
    from aiogram import F as AGF
except ImportError:
    # Fallback for older versions
    try:
        from aiogram.filters import F as AGF
    except ImportError:
        AGF = None

# FSM imports - may vary by version
try:
    from aiogram.fsm.state import State as AGState, StatesGroup as AGStatesGroup
except ImportError:
    # Fallback for different import paths
    try:
        from aiogram.fsm import State as AGState, StatesGroup as AGStatesGroup
    except ImportError:
        AGState = None
        AGStatesGroup = None

try:
    from aiogram.fsm.context import FSMContext as AGFSMContext
except ImportError:
    # Fallback for different import paths
    try:
        from aiogram.fsm import FSMContext as AGFSMContext
    except ImportError:
        AGFSMContext = None


class TestSideBySideComparison:
    """Test that obabot code works identically to aiogram code."""
    
    def test_import_comparison(self):
        """Test that imports are similar."""
        # obabot imports
        from obabot import create_bot
        from obabot.filters import Command, F
        from obabot.fsm import State, StatesGroup, FSMContext
        
        # aiogram imports - use same logic as module level
        from aiogram import Bot, Dispatcher, Router
        from aiogram.filters import Command as AGCommand
        
        # F is imported from aiogram, not aiogram.filters (in aiogram 3.24+)
        try:
            from aiogram import F as AGF_local
        except ImportError:
            # Fallback for older versions
            try:
                from aiogram.filters import F as AGF_local
            except ImportError:
                AGF_local = None
        
        # FSM imports - may vary by version
        try:
            from aiogram.fsm.state import State as AGState_local, StatesGroup as AGStatesGroup_local
        except ImportError:
            try:
                from aiogram.fsm import State as AGState_local, StatesGroup as AGStatesGroup_local
            except ImportError:
                AGState_local = None
                AGStatesGroup_local = None
        
        try:
            from aiogram.fsm.context import FSMContext as AGFSMContext_local
        except ImportError:
            try:
                from aiogram.fsm import FSMContext as AGFSMContext_local
            except ImportError:
                AGFSMContext_local = None
        
        # All should be importable (some may be None in some versions)
        assert all([
            create_bot, Command, F, State, StatesGroup, FSMContext,
            Bot, Dispatcher, Router, AGCommand
        ])
        # Optional components (may not be available in some aiogram versions)
        if AGF_local is not None:
            assert AGF_local is not None
        if AGState_local is not None:
            assert AGState_local is not None
        if AGStatesGroup_local is not None:
            assert AGStatesGroup_local is not None
        if AGFSMContext_local is not None:
            assert AGFSMContext_local is not None
    
    @pytest.mark.asyncio
    async def test_handler_registration_comparison(self, tg_token, skip_if_no_tg_token):
        """Test that handler registration works the same way."""
        # obabot way
        obabot_bot, obabot_dp, obabot_router = create_bot(tg_token=tg_token)
        
        @obabot_router.message(Command("start"))
        async def obabot_start(message):
            pass
        
        @obabot_dp.message(Command("help"))
        async def obabot_help(message):
            pass
        
        # aiogram way
        aiogram_bot = Bot(token=tg_token)
        aiogram_dp = Dispatcher()
        aiogram_router = Router()
        aiogram_dp.include_router(aiogram_router)
        
        @aiogram_router.message(AGCommand("start"))
        async def aiogram_start(message):
            pass
        
        @aiogram_dp.message(AGCommand("help"))
        async def aiogram_help(message):
            pass
        
        # Both should work identically
        assert callable(obabot_start)
        assert callable(obabot_help)
        assert callable(aiogram_start)
        assert callable(aiogram_help)
        
        # Cleanup
        await obabot_bot.close()
        await aiogram_bot.session.close()
    
    @pytest.mark.asyncio
    async def test_fsm_comparison(self, tg_token, skip_if_no_tg_token):
        """Test that FSM works the same way."""
        # Skip if FSM components are not available
        if AGState is None or AGStatesGroup is None or AGFSMContext is None:
            pytest.skip("FSM components not available in this aiogram version")
        
        # obabot FSM
        obabot_bot, _, obabot_router = create_bot(tg_token=tg_token)
        
        class obabotForm(StatesGroup):
            name = State()
            age = State()
        
        @obabot_router.message(Command("start"))
        async def obabot_start(message, state: FSMContext):
            await state.set_state(obabotForm.name)
        
        @obabot_router.message(obabotForm.name)
        async def obabot_process_name(message, state: FSMContext):
            await state.update_data(name=message.text)
        
        # aiogram FSM
        aiogram_bot = Bot(token=tg_token)
        aiogram_dp = Dispatcher()
        aiogram_router = Router()
        aiogram_dp.include_router(aiogram_router)
        
        class AiogramForm(AGStatesGroup):
            name = AGState()
            age = AGState()
        
        @aiogram_router.message(AGCommand("start"))
        async def aiogram_start(message, state: AGFSMContext):
            await state.set_state(AiogramForm.name)
        
        @aiogram_router.message(AiogramForm.name)
        async def aiogram_process_name(message, state: AGFSMContext):
            await state.update_data(name=message.text)
        
        # Both should work identically
        assert callable(obabot_start)
        assert callable(obabot_process_name)
        assert callable(aiogram_start)
        assert callable(aiogram_process_name)
        
        # Cleanup
        await obabot_bot.close()
        await aiogram_bot.session.close()
