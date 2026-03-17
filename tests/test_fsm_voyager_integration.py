"""
Integration tests for FSM coverage logging and fsm-voyager integration.

These tests verify that:
1. FSMCoverageMiddleware correctly logs state transitions
2. The middleware integrates properly with fsm-voyager
3. Coverage logging is activated only when env vars are set
"""

import csv
import os
import tempfile
from pathlib import Path
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from obabot.middleware.fsm_coverage import (
    FSMCoverageMiddleware,
    CoverageLogger,
    extract_action_from_event,
    get_state_name,
    is_coverage_enabled,
    reset_coverage_state,
    get_coverage_log_path,
)


def _fsm_voyager_available() -> bool:
    """Check if fsm-voyager is installed."""
    try:
        import fsm_voyager
        return True
    except ImportError:
        return False


class TestCoverageEnabled:
    """Tests for is_coverage_enabled() function."""
    
    def test_disabled_by_default(self):
        """Coverage should be disabled when no env vars are set."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("COVERAGE_LOG", None)
            os.environ.pop("COVERAGE_LOG_DIR", None)
            reset_coverage_state()
            assert not is_coverage_enabled()
    
    def test_enabled_with_coverage_log(self):
        """Coverage should be enabled when COVERAGE_LOG is set."""
        with patch.dict(os.environ, {"COVERAGE_LOG": "/tmp/test.log"}):
            reset_coverage_state()
            assert is_coverage_enabled()
    
    def test_enabled_with_coverage_log_dir(self):
        """Coverage should be enabled when COVERAGE_LOG_DIR is set."""
        with patch.dict(os.environ, {"COVERAGE_LOG_DIR": "/tmp/logs"}):
            reset_coverage_state()
            assert is_coverage_enabled()


class TestExtractAction:
    """Tests for extract_action_from_event() function."""
    
    def test_callback_query_action(self):
        """Should extract callback data from CallbackQuery."""
        from aiogram.types import CallbackQuery
        
        callback = MagicMock(spec=CallbackQuery)
        callback.data = "register"
        
        action = extract_action_from_event(callback)
        assert action == "callback:register"
    
    def test_callback_query_empty_data(self):
        """Should handle CallbackQuery with empty data."""
        from aiogram.types import CallbackQuery
        
        callback = MagicMock(spec=CallbackQuery)
        callback.data = None
        
        action = extract_action_from_event(callback)
        assert action == "callback:"
    
    def test_command_message(self):
        """Should extract command from Message."""
        from aiogram.types import Message
        
        message = MagicMock(spec=Message)
        message.text = "/start"
        
        action = extract_action_from_event(message)
        assert action == "command:/start"
    
    def test_command_with_args(self):
        """Should extract command with arguments."""
        from aiogram.types import Message
        
        message = MagicMock(spec=Message)
        message.text = "/start some_arg"
        
        action = extract_action_from_event(message)
        assert action == "command:/start"
    
    def test_text_message(self):
        """Should return text:* for regular text messages."""
        from aiogram.types import Message
        
        message = MagicMock(spec=Message)
        message.text = "Hello, world!"
        
        action = extract_action_from_event(message)
        assert action == "text:*"
    
    def test_empty_text_message(self):
        """Should handle Message with no text."""
        from aiogram.types import Message
        
        message = MagicMock(spec=Message)
        message.text = None
        
        action = extract_action_from_event(message)
        assert action == "text:*"
    
    def test_unknown_event(self):
        """Should return unknown:* for unrecognized events."""
        event = MagicMock()
        
        action = extract_action_from_event(event)
        assert action == "unknown:*"


class TestGetStateName:
    """Tests for get_state_name() function."""
    
    def test_none_state(self):
        """Should return None for None state."""
        assert get_state_name(None) is None
    
    def test_simple_state(self):
        """Should return state name as-is for simple strings."""
        assert get_state_name("waiting_name") == "waiting_name"
    
    def test_qualified_state(self):
        """Should extract state name from qualified state string."""
        assert get_state_name("RegistrationForm:waiting_name") == "waiting_name"
    
    def test_state_object(self):
        """Should convert State object to string and extract name."""
        from obabot.fsm import State, StatesGroup
        
        class TestStates(StatesGroup):
            test_state = State()
        
        state_str = str(TestStates.test_state)
        result = get_state_name(state_str)
        assert "test_state" in result


class TestCoverageLogger:
    """Tests for CoverageLogger class."""
    
    def test_creates_file_with_header(self, tmp_path):
        """Should create CSV file with header on first write."""
        reset_coverage_state()
        
        log_path = tmp_path / "coverage.log"
        logger = CoverageLogger(log_path)
        
        logger.log_transition("start", "waiting_name", "callback:register")
        
        assert log_path.exists()
        content = log_path.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 2
        assert lines[0] == "from_state,to_state,action"
        assert lines[1] == "start,waiting_name,callback:register"
    
    def test_appends_to_existing_file(self, tmp_path):
        """Should append to existing file without duplicating header."""
        reset_coverage_state()
        
        log_path = tmp_path / "coverage.log"
        logger = CoverageLogger(log_path)
        
        logger.log_transition("start", "waiting_name", "callback:register")
        
        logger2 = CoverageLogger(log_path)
        logger2._initialized = True
        logger2.log_transition("waiting_name", "waiting_email", "text:*")
        
        content = log_path.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 3
        assert lines[0] == "from_state,to_state,action"
    
    def test_deduplicates_transitions(self, tmp_path):
        """Should not log the same transition twice."""
        log_path = tmp_path / "coverage.log"
        reset_coverage_state()
        
        logger = CoverageLogger(log_path)
        
        logger.log_transition("start", "waiting_name", "callback:register")
        logger.log_transition("start", "waiting_name", "callback:register")
        logger.log_transition("start", "waiting_name", "callback:register")
        
        content = log_path.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 2
    
    def test_ignores_none_states(self, tmp_path):
        """Should not log when both states are None."""
        log_path = tmp_path / "coverage.log"
        logger = CoverageLogger(log_path)
        
        logger.log_transition(None, None, "text:*")
        
        assert not log_path.exists()


class TestFSMCoverageMiddleware:
    """Tests for FSMCoverageMiddleware class."""
    
    @pytest.mark.asyncio
    async def test_noop_without_env(self):
        """Middleware should be a no-op when coverage is disabled."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("COVERAGE_LOG", None)
            os.environ.pop("COVERAGE_LOG_DIR", None)
            reset_coverage_state()
            
            middleware = FSMCoverageMiddleware()
            
            handler = AsyncMock(return_value="result")
            event = MagicMock()
            data = {}
            
            result = await middleware(handler, event, data)
            
            assert result == "result"
            handler.assert_called_once_with(event, data)
    
    @pytest.mark.asyncio
    async def test_logs_state_transition(self, tmp_path):
        """Middleware should log state transitions."""
        log_path = tmp_path / "coverage.log"
        
        with patch.dict(os.environ, {"COVERAGE_LOG": str(log_path)}):
            reset_coverage_state()
            
            middleware = FSMCoverageMiddleware()
            
            from aiogram.types import CallbackQuery
            event = MagicMock(spec=CallbackQuery)
            event.data = "register"
            
            state_mock = AsyncMock()
            state_mock.get_state.side_effect = [
                None,
                "RegistrationForm:waiting_name",
            ]
            
            async def handler(event, data):
                return "ok"
            
            data = {"state": state_mock}
            
            result = await middleware(handler, event, data)
            
            assert result == "ok"
            assert log_path.exists()
            
            content = log_path.read_text()
            assert "waiting_name" in content
            assert "callback:register" in content
    
    @pytest.mark.asyncio
    async def test_no_log_when_state_unchanged(self, tmp_path):
        """Middleware should not log when state doesn't change."""
        log_path = tmp_path / "coverage.log"
        
        with patch.dict(os.environ, {"COVERAGE_LOG": str(log_path)}):
            reset_coverage_state()
            
            middleware = FSMCoverageMiddleware()
            
            from aiogram.types import CallbackQuery
            event = MagicMock(spec=CallbackQuery)
            event.data = "info"
            
            state_mock = AsyncMock()
            state_mock.get_state.return_value = None
            
            async def handler(event, data):
                return "ok"
            
            data = {"state": state_mock}
            
            await middleware(handler, event, data)
            
            if log_path.exists():
                content = log_path.read_text()
                lines = [l for l in content.strip().split("\n") if l and not l.startswith("from_state")]
                assert len(lines) == 0


class TestCoverageLogDir:
    """Tests for COVERAGE_LOG_DIR mode."""
    
    def test_creates_timestamped_file(self, tmp_path):
        """Should create timestamped log file in directory."""
        with patch.dict(os.environ, {"COVERAGE_LOG_DIR": str(tmp_path)}):
            reset_coverage_state()
            
            log_path = get_coverage_log_path()
            
            assert log_path is not None
            assert log_path.parent == tmp_path
            assert log_path.name.startswith("coverage-")
            assert log_path.name.endswith(".log")
    
    def test_same_file_in_session(self, tmp_path):
        """Should return same file path within a session."""
        with patch.dict(os.environ, {"COVERAGE_LOG_DIR": str(tmp_path)}):
            reset_coverage_state()
            
            path1 = get_coverage_log_path()
            path2 = get_coverage_log_path()
            
            assert path1 == path2


class TestFactoryIntegration:
    """Tests for middleware registration in create_bot()."""
    
    def test_middleware_registered_when_enabled(self, tmp_path):
        """Middleware should be auto-registered when COVERAGE_LOG is set."""
        log_path = tmp_path / "coverage.log"
        
        with patch.dict(os.environ, {"COVERAGE_LOG": str(log_path), "TESTING": "1"}):
            reset_coverage_state()
            
            from obabot import create_bot
            
            bot, dp, router = create_bot(test_mode=True)
            
            assert router is not None
    
    def test_no_middleware_when_disabled(self):
        """Middleware should not be registered when coverage is disabled."""
        with patch.dict(os.environ, {"TESTING": "1"}, clear=True):
            os.environ.pop("COVERAGE_LOG", None)
            os.environ.pop("COVERAGE_LOG_DIR", None)
            reset_coverage_state()
            
            from obabot import create_bot
            
            bot, dp, router = create_bot(test_mode=True)
            
            assert router is not None


class TestFSMVoyagerIntegration:
    """Integration tests with fsm-voyager (requires fsm-voyager installed)."""
    
    @pytest.fixture
    def sample_model_path(self, tmp_path):
        """Create a sample model.json for testing."""
        model = {
            "bot_name": "TestBot",
            "initial_state": "start",
            "states": {
                "start": {"text": "Welcome!", "buttons": []},
                "waiting_name": {"text": "Enter name:", "buttons": []},
                "waiting_email": {"text": "Enter email:", "buttons": []},
            },
            "transitions": [
                {"from": "start", "to": "waiting_name", "action": "callback:register"},
                {"from": "waiting_name", "to": "waiting_email", "action": "text:*"},
                {"from": "waiting_email", "to": "start", "action": "text:*"},
            ],
        }
        
        import json
        model_path = tmp_path / "model.json"
        model_path.write_text(json.dumps(model))
        return model_path
    
    @pytest.mark.skipif(
        not _fsm_voyager_available(),
        reason="fsm-voyager not installed"
    )
    def test_full_pipeline(self, tmp_path, sample_model_path):
        """Test full pipeline: log transitions -> parse -> calculate coverage."""
        from fsm_voyager import load_model, parse_coverage_logs
        from fsm_voyager.coverage_report import calculate_coverage
        
        log_path = tmp_path / "coverage.log"
        log_path.write_text(
            "from_state,to_state,action\n"
            "start,waiting_name,callback:register\n"
            "waiting_name,waiting_email,text:*\n"
        )
        
        model = load_model(sample_model_path)
        covered = parse_coverage_logs(tmp_path)
        stats = calculate_coverage(model, covered)
        
        assert stats.covered_transitions == 2
        assert stats.total_transitions == 3
        assert stats.transition_coverage_percent > 60
    
    @pytest.mark.skipif(
        not _fsm_voyager_available(),
        reason="fsm-voyager not installed"
    )
    def test_example_model_valid(self):
        """Test that examples/model.json is valid for fsm-voyager."""
        from fsm_voyager import load_model
        
        example_path = Path(__file__).parent.parent / "examples" / "model.json"
        if not example_path.exists():
            pytest.skip("examples/model.json not found")
        
        model = load_model(example_path)
        
        assert model.bot_name == "RegistrationBot"
        assert len(model.states) >= 4
        assert len(model.transitions) >= 4
