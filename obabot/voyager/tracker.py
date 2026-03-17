"""
Chain tracker for pytest integration.

Provides fixtures and utilities for tracking navigation chains during tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from obabot.voyager.chain_analyzer import ChainAnalyzer, ChainReport, NavigationChain, TransitionRecord
from obabot.voyager.depth_calculator import DepthCalculator


@dataclass
class TestChain:
    """Chain recorded during a single test."""
    
    test_name: str
    session_id: str
    transitions: List[TransitionRecord] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds() * 1000
    
    @property
    def max_depth(self) -> int:
        if not self.transitions:
            return 0
        return max(t.depth for t in self.transitions)
    
    @property
    def callbacks(self) -> List[str]:
        return [f"{t.trigger_type}:{t.trigger_data}" for t in self.transitions]


class ChainTracker:
    """
    Tracks navigation chains during test execution.
    
    Usage with pytest:
        @pytest.fixture(scope="session")
        def voyager_tracker():
            tracker = ChainTracker()
            yield tracker
            tracker.print_report()
            tracker.save("coverage/chains.json")
        
        @pytest.fixture(autouse=True)
        def track_test_chain(request, voyager_tracker):
            voyager_tracker.start_chain(request.node.name)
            yield
            voyager_tracker.end_chain()
    
    Manual usage:
        tracker = ChainTracker()
        tracker.start_chain("test_booking_flow")
        
        # ... test code that logs transitions ...
        
        tracker.end_chain()
        tracker.print_report()
    """
    
    def __init__(self, depth_calculator: Optional[DepthCalculator] = None):
        self._depth_calculator = depth_calculator or DepthCalculator()
        self._chains: Dict[str, TestChain] = {}
        self._current_chain: Optional[TestChain] = None
        self._current_depth: int = 0
        self._session_counter: int = 0
        self._all_transitions: List[TransitionRecord] = []
    
    def start_chain(self, test_name: str) -> str:
        """
        Start tracking a new chain.
        
        Args:
            test_name: Name of the test (used as identifier)
        
        Returns:
            Session ID for this chain
        """
        self._session_counter += 1
        session_id = f"test_{self._session_counter}_{test_name[:50]}"
        
        self._current_chain = TestChain(
            test_name=test_name,
            session_id=session_id,
            start_time=datetime.now(),
        )
        self._current_depth = 0
        self._chains[session_id] = self._current_chain
        
        return session_id
    
    def end_chain(self) -> Optional[TestChain]:
        """End the current chain and return it."""
        if self._current_chain is None:
            return None
        
        self._current_chain.end_time = datetime.now()
        chain = self._current_chain
        self._current_chain = None
        self._current_depth = 0
        
        return chain
    
    def log_transition(
        self,
        from_state: Optional[str],
        to_state: Optional[str],
        trigger_type: str,
        trigger_data: str,
        user_id: str = "",
    ) -> None:
        """
        Log a transition to the current chain.
        
        Args:
            from_state: Source state
            to_state: Target state
            trigger_type: Type of trigger (callback, command, text)
            trigger_data: Trigger data (callback data, command, etc.)
            user_id: User ID (optional)
        """
        if self._current_chain is None:
            return
        
        callback_data = f"{trigger_type}:{trigger_data}"
        new_depth = self._depth_calculator.calculate(
            self._current_depth,
            callback_data,
            from_state=from_state,
            to_state=to_state,
        )
        is_back = self._depth_calculator.detect_is_back(
            callback_data,
            self._current_depth,
            new_depth,
        )
        
        record = TransitionRecord(
            timestamp=datetime.now(),
            user_id=user_id,
            session_id=self._current_chain.session_id,
            from_state=from_state or "",
            to_state=to_state or "",
            trigger_type=trigger_type,
            trigger_data=trigger_data,
            depth=new_depth,
            is_back=is_back,
        )
        
        self._current_chain.transitions.append(record)
        self._all_transitions.append(record)
        self._current_depth = new_depth
    
    @property
    def current_depth(self) -> int:
        """Get current navigation depth."""
        return self._current_depth
    
    @property
    def current_session_id(self) -> Optional[str]:
        """Get current session ID."""
        return self._current_chain.session_id if self._current_chain else None
    
    def get_chain(self, session_id: str) -> Optional[TestChain]:
        """Get a chain by session ID."""
        return self._chains.get(session_id)
    
    def get_all_chains(self) -> List[TestChain]:
        """Get all recorded chains."""
        return list(self._chains.values())
    
    def analyze(self) -> ChainReport:
        """Analyze all recorded chains."""
        analyzer = ChainAnalyzer()
        analyzer.load_records(self._all_transitions)
        return analyzer.analyze()
    
    def print_report(self) -> None:
        """Print a summary report to stdout."""
        report = self.analyze()
        
        print("\n" + "=" * 60)
        print("FSM Navigation Chain Report")
        print("=" * 60)
        
        print(f"\nTotal transitions: {report.total_transitions}")
        print(f"Total test chains: {len(self._chains)}")
        
        print(f"\nDepth metrics:")
        print(f"  Max depth: {report.max_depth}")
        print(f"  Avg depth: {report.avg_depth:.2f}")
        
        print(f"\nChain metrics:")
        print(f"  Max chain length: {report.max_chain_length}")
        print(f"  Avg chain length: {report.avg_chain_length:.2f}")
        
        print(f"\nNavigation:")
        print(f"  Back usage ratio: {report.back_usage_ratio:.1%}")
        print(f"  Total back navigations: {report.total_back_navigations}")
        
        if report.dead_ends:
            print(f"\nDead ends ({len(report.dead_ends)}):")
            for state in sorted(report.dead_ends):
                print(f"  - {state}")
        
        if report.orphan_states:
            print(f"\nOrphan states ({len(report.orphan_states)}):")
            for state in sorted(report.orphan_states):
                print(f"  - {state}")
        
        if report.deepest_chains:
            print(f"\nDeepest chains:")
            for chain in report.deepest_chains[:5]:
                print(f"  - {chain.session_id}: depth={chain.max_depth}, length={chain.length}")
        
        print("\n" + "=" * 60)
    
    def save(self, path: str) -> None:
        """Save chains to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "generated_at": datetime.now().isoformat(),
            "total_chains": len(self._chains),
            "total_transitions": len(self._all_transitions),
            "chains": [
                {
                    "test_name": chain.test_name,
                    "session_id": chain.session_id,
                    "max_depth": chain.max_depth,
                    "length": len(chain.transitions),
                    "duration_ms": chain.duration_ms,
                    "callbacks": chain.callbacks,
                }
                for chain in self._chains.values()
            ],
            "report": self.analyze().to_dict(),
        }
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def export_mermaid(self, path: str) -> None:
        """Export navigation graph as Mermaid diagram."""
        analyzer = ChainAnalyzer()
        analyzer.load_records(self._all_transitions)
        analyzer.export_mermaid(path)


def pytest_configure_voyager():
    """
    Returns pytest fixtures for chain tracking.
    
    Add to conftest.py:
        from obabot.voyager import pytest_configure_voyager
        voyager_tracker, track_test_chain = pytest_configure_voyager()
    
    Or copy the fixtures directly.
    """
    import pytest
    
    @pytest.fixture(scope="session")
    def voyager_tracker():
        tracker = ChainTracker()
        yield tracker
        tracker.print_report()
    
    @pytest.fixture(autouse=True)
    def track_test_chain(request, voyager_tracker):
        voyager_tracker.start_chain(request.node.name)
        yield
        voyager_tracker.end_chain()
    
    return voyager_tracker, track_test_chain
