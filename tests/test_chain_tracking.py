"""Tests for chain tracking functionality."""

import csv
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from obabot.voyager import ChainAnalyzer, ChainReport, NavigationChain, DepthCalculator, ChainTracker
from obabot.voyager.chain_analyzer import TransitionRecord


class TestDepthCalculator:
    """Tests for DepthCalculator."""
    
    def test_main_menu_resets_depth(self):
        calc = DepthCalculator()
        assert calc.calculate(5, "nav:main") == 0
        assert calc.calculate(3, "nv:main") == 0
        assert calc.calculate(10, "employee:menu") == 0
    
    def test_back_navigation_decreases_depth(self):
        calc = DepthCalculator()
        assert calc.calculate(3, "nav:back") == 2
        assert calc.calculate(1, "some:back:action") == 0
        assert calc.calculate(0, "nav:back") == 0
        assert calc.calculate(2, "callback:back") == 1
    
    def test_role_selection_sets_depth_to_one(self):
        calc = DepthCalculator()
        assert calc.calculate(0, "cr:admin") == 1
        assert calc.calculate(5, "choose_role:user") == 1
    
    def test_other_transitions_increase_depth(self):
        calc = DepthCalculator()
        assert calc.calculate(0, "catalog:view") == 1
        assert calc.calculate(2, "item:select") == 3
        assert calc.calculate(1, "action:next") == 2
    
    def test_custom_patterns(self):
        calc = DepthCalculator()
        calc.add_main_menu_pattern("custom:home")
        calc.add_back_pattern(":return:")
        calc.add_role_pattern("role:")
        
        assert calc.calculate(5, "custom:home") == 0
        assert calc.calculate(3, "go:return:now") == 2
        assert calc.calculate(0, "role:admin") == 1
    
    def test_is_back_navigation(self):
        calc = DepthCalculator()
        assert calc.is_back_navigation("nav:back") is True
        assert calc.is_back_navigation("some:back:thing") is True
        assert calc.is_back_navigation("callback:back") is True
        assert calc.is_back_navigation("action_back") is True
        assert calc.is_back_navigation("catalog:view") is False
        assert calc.is_back_navigation("item:next") is False
    
    def test_detect_is_back(self):
        calc = DepthCalculator()
        assert calc.detect_is_back("nav:back", 3, 2) is True
        assert calc.detect_is_back("catalog:view", 2, 3) is False
        assert calc.detect_is_back("nav:main", 3, 0) is True
        assert calc.detect_is_back("some:action", 3, 2) is True


class TestTransitionRecord:
    """Tests for TransitionRecord."""
    
    def test_from_row_extended(self):
        row = [
            "2024-01-01T12:00:00",
            "123",
            "sess_abc",
            "start",
            "catalog",
            "callback",
            "catalog",
            "1",
            "false",
        ]
        record = TransitionRecord.from_row(row)
        
        assert record.user_id == "123"
        assert record.session_id == "sess_abc"
        assert record.from_state == "start"
        assert record.to_state == "catalog"
        assert record.trigger_type == "callback"
        assert record.trigger_data == "catalog"
        assert record.depth == 1
        assert record.is_back is False
    
    def test_from_simple_row(self):
        row = ["start", "catalog", "callback:catalog"]
        record = TransitionRecord.from_simple_row(row, "test_session")
        
        assert record.from_state == "start"
        assert record.to_state == "catalog"
        assert record.trigger_type == "callback"
        assert record.trigger_data == "catalog"
        assert record.session_id == "test_session"


class TestNavigationChain:
    """Tests for NavigationChain."""
    
    def test_empty_chain(self):
        chain = NavigationChain(session_id="test", user_id="123")
        assert chain.length == 0
        assert chain.max_depth == 0
        assert chain.states == []
        assert chain.back_ratio == 0.0
    
    def test_chain_with_transitions(self):
        chain = NavigationChain(session_id="test", user_id="123")
        chain.transitions = [
            TransitionRecord(
                timestamp=datetime.now(),
                user_id="123",
                session_id="test",
                from_state="start",
                to_state="catalog",
                trigger_type="callback",
                trigger_data="catalog",
                depth=1,
                is_back=False,
            ),
            TransitionRecord(
                timestamp=datetime.now(),
                user_id="123",
                session_id="test",
                from_state="catalog",
                to_state="item",
                trigger_type="callback",
                trigger_data="item_1",
                depth=2,
                is_back=False,
            ),
            TransitionRecord(
                timestamp=datetime.now(),
                user_id="123",
                session_id="test",
                from_state="item",
                to_state="catalog",
                trigger_type="callback",
                trigger_data="nav:back",
                depth=1,
                is_back=True,
            ),
        ]
        
        assert chain.length == 3
        assert chain.max_depth == 2
        assert chain.states == ["start", "catalog", "item", "catalog"]
        assert chain.back_count == 1
        assert chain.back_ratio == pytest.approx(1/3, rel=0.01)


class TestChainAnalyzer:
    """Tests for ChainAnalyzer."""
    
    def test_load_simple_csv(self, tmp_path):
        csv_path = tmp_path / "coverage.log"
        csv_path.write_text(
            "from_state,to_state,action\n"
            "start,catalog,callback:catalog\n"
            "catalog,item,callback:item_1\n"
            "item,catalog,callback:nav:back\n"
        )
        
        analyzer = ChainAnalyzer()
        analyzer.load_csv(csv_path)
        
        report = analyzer.analyze()
        assert report.total_transitions == 3
        assert "start" in report.all_states
        assert "catalog" in report.all_states
        assert "item" in report.all_states
    
    def test_dead_ends_detection(self, tmp_path):
        csv_path = tmp_path / "coverage.log"
        csv_path.write_text(
            "from_state,to_state,action\n"
            "start,catalog,callback:catalog\n"
            "catalog,dead_end,callback:dead\n"
        )
        
        analyzer = ChainAnalyzer()
        analyzer.load_csv(csv_path)
        report = analyzer.analyze()
        
        assert "dead_end" in report.dead_ends
    
    def test_orphan_detection(self, tmp_path):
        csv_path = tmp_path / "coverage.log"
        csv_path.write_text(
            "from_state,to_state,action\n"
            "start,catalog,callback:catalog\n"
            "orphan,somewhere,callback:go\n"
        )
        
        analyzer = ChainAnalyzer()
        analyzer.load_csv(csv_path)
        report = analyzer.analyze(initial_state="start")
        
        assert "orphan" in report.orphan_states
        assert "start" not in report.orphan_states
    
    def test_most_used_transitions(self, tmp_path):
        csv_path = tmp_path / "coverage.log"
        csv_path.write_text(
            "from_state,to_state,action\n"
            "start,catalog,callback:catalog\n"
            "start,catalog,callback:catalog\n"
            "start,catalog,callback:catalog\n"
            "catalog,item,callback:item\n"
        )
        
        analyzer = ChainAnalyzer()
        analyzer.load_csv(csv_path)
        
        top = analyzer.get_most_used_transitions(top=5)
        assert len(top) == 2
        assert top[0] == ("start", "catalog", 3)
    
    def test_export_mermaid(self, tmp_path):
        csv_path = tmp_path / "coverage.log"
        csv_path.write_text(
            "from_state,to_state,action\n"
            "start,catalog,callback:catalog\n"
            "catalog,item,callback:item\n"
        )
        
        analyzer = ChainAnalyzer()
        analyzer.load_csv(csv_path)
        
        output_path = tmp_path / "graph.md"
        analyzer.export_mermaid(output_path)
        
        content = output_path.read_text()
        assert "stateDiagram-v2" in content
        assert "start" in content
        assert "catalog" in content
        assert "Metrics" in content
    
    def test_export_json(self, tmp_path):
        import json
        
        csv_path = tmp_path / "coverage.log"
        csv_path.write_text(
            "from_state,to_state,action\n"
            "start,catalog,callback:catalog\n"
        )
        
        analyzer = ChainAnalyzer()
        analyzer.load_csv(csv_path)
        
        output_path = tmp_path / "report.json"
        analyzer.export_json(output_path)
        
        data = json.loads(output_path.read_text())
        assert data["total_transitions"] == 1
        assert "start" in data["all_states"]


class TestChainTracker:
    """Tests for ChainTracker."""
    
    def test_start_end_chain(self):
        tracker = ChainTracker()
        
        session_id = tracker.start_chain("test_booking_flow")
        assert session_id is not None
        assert tracker.current_session_id == session_id
        
        chain = tracker.end_chain()
        assert chain is not None
        assert chain.test_name == "test_booking_flow"
        assert tracker.current_session_id is None
    
    def test_log_transitions(self):
        tracker = ChainTracker()
        tracker.start_chain("test_flow")
        
        tracker.log_transition("start", "catalog", "callback", "catalog")
        tracker.log_transition("catalog", "item", "callback", "item_1")
        
        chain = tracker.end_chain()
        assert len(chain.transitions) == 2
        assert chain.transitions[0].from_state == "start"
        assert chain.transitions[1].to_state == "item"
    
    def test_depth_tracking(self):
        tracker = ChainTracker()
        tracker.start_chain("test_depth")
        
        assert tracker.current_depth == 0
        
        tracker.log_transition("start", "catalog", "catalog", "view")
        assert tracker.current_depth == 1
        
        tracker.log_transition("catalog", "item", "item", "select")
        assert tracker.current_depth == 2
        
        tracker.log_transition("item", "catalog", "nav", "back")
        assert tracker.current_depth == 1
        
        tracker.end_chain()
    
    def test_analyze(self):
        tracker = ChainTracker()
        
        tracker.start_chain("test_1")
        tracker.log_transition("start", "a", "callback", "a")
        tracker.log_transition("a", "b", "callback", "b")
        tracker.end_chain()
        
        tracker.start_chain("test_2")
        tracker.log_transition("start", "x", "callback", "x")
        tracker.end_chain()
        
        report = tracker.analyze()
        assert report.total_transitions == 3
        assert report.total_sessions == 2
    
    def test_save_and_export(self, tmp_path):
        tracker = ChainTracker()
        
        tracker.start_chain("test_save")
        tracker.log_transition("start", "end", "callback", "go")
        tracker.end_chain()
        
        json_path = tmp_path / "chains.json"
        tracker.save(str(json_path))
        assert json_path.exists()
        
        md_path = tmp_path / "graph.md"
        tracker.export_mermaid(str(md_path))
        assert md_path.exists()


class TestExtendedCoverageFormat:
    """Tests for extended coverage format in middleware."""
    
    def test_extended_format_header(self, tmp_path, monkeypatch):
        from obabot.middleware.fsm_coverage import CoverageLogger, reset_coverage_state
        
        reset_coverage_state()
        
        log_path = tmp_path / "extended.log"
        logger = CoverageLogger(log_path, extended=True)
        
        logger.log_transition_extended(
            from_state="start",
            to_state="catalog",
            trigger_type="callback",
            trigger_data="catalog",
            user_id="123",
            session_id="sess_abc",
            depth=1,
            is_back=False,
        )
        
        content = log_path.read_text()
        assert "timestamp" in content
        assert "user_id" in content
        assert "session_id" in content
        assert "depth" in content
        assert "is_back" in content
    
    def test_extended_format_values(self, tmp_path):
        from obabot.middleware.fsm_coverage import CoverageLogger, reset_coverage_state
        
        reset_coverage_state()
        
        log_path = tmp_path / "extended.log"
        logger = CoverageLogger(log_path, extended=True)
        
        logger.log_transition_extended(
            from_state="start",
            to_state="catalog",
            trigger_type="callback",
            trigger_data="catalog",
            user_id="123",
            session_id="sess_abc",
            depth=1,
            is_back=False,
        )
        
        with open(log_path, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        assert len(rows) == 2
        data_row = rows[1]
        assert data_row[1] == "123"
        assert data_row[2] == "sess_abc"
        assert data_row[3] == "start"
        assert data_row[4] == "catalog"
        assert data_row[7] == "1"
        assert data_row[8] == "false"


class TestChainReport:
    """Tests for ChainReport."""
    
    def test_to_dict(self):
        report = ChainReport(
            total_transitions=10,
            total_sessions=3,
            max_depth=5,
            avg_depth=2.5,
            dead_ends={"state_a", "state_b"},
            orphan_states={"orphan_1"},
        )
        
        data = report.to_dict()
        
        assert data["total_transitions"] == 10
        assert data["total_sessions"] == 3
        assert data["max_depth"] == 5
        assert data["avg_depth"] == 2.5
        assert "state_a" in data["dead_ends"]
        assert "orphan_1" in data["orphan_states"]
