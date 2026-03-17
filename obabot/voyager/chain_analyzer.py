"""
Chain analyzer for FSM navigation tracking.

Analyzes navigation chains, calculates metrics, detects dead ends and orphans.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union


@dataclass
class TransitionRecord:
    """Single transition record from extended log."""
    
    timestamp: datetime
    user_id: str
    session_id: str
    from_state: str
    to_state: str
    trigger_type: str
    trigger_data: str
    depth: int
    is_back: bool
    
    @classmethod
    def from_row(cls, row: List[str]) -> "TransitionRecord":
        """Parse from CSV row."""
        return cls(
            timestamp=datetime.fromisoformat(row[0]) if row[0] else datetime.now(),
            user_id=row[1] if len(row) > 1 else "",
            session_id=row[2] if len(row) > 2 else "",
            from_state=row[3] if len(row) > 3 else "",
            to_state=row[4] if len(row) > 4 else "",
            trigger_type=row[5] if len(row) > 5 else "",
            trigger_data=row[6] if len(row) > 6 else "",
            depth=int(row[7]) if len(row) > 7 and row[7].isdigit() else 0,
            is_back=row[8].lower() in ("true", "1", "yes") if len(row) > 8 else False,
        )
    
    @classmethod
    def from_simple_row(cls, row: List[str], session_id: str = "default") -> "TransitionRecord":
        """Parse from simple CSV row (from_state,to_state,action)."""
        from_state = row[0] if len(row) > 0 else ""
        to_state = row[1] if len(row) > 1 else ""
        action = row[2] if len(row) > 2 else ""
        
        trigger_type = "unknown"
        trigger_data = action
        if ":" in action:
            trigger_type, trigger_data = action.split(":", 1)
        
        return cls(
            timestamp=datetime.now(),
            user_id="",
            session_id=session_id,
            from_state=from_state,
            to_state=to_state,
            trigger_type=trigger_type,
            trigger_data=trigger_data,
            depth=0,
            is_back=False,
        )


@dataclass
class NavigationChain:
    """A sequence of transitions within a session."""
    
    session_id: str
    user_id: str
    transitions: List[TransitionRecord] = field(default_factory=list)
    
    @property
    def length(self) -> int:
        return len(self.transitions)
    
    @property
    def max_depth(self) -> int:
        if not self.transitions:
            return 0
        return max(t.depth for t in self.transitions)
    
    @property
    def states(self) -> List[str]:
        """Get ordered list of visited states."""
        if not self.transitions:
            return []
        result = [self.transitions[0].from_state]
        for t in self.transitions:
            if t.to_state:
                result.append(t.to_state)
        return result
    
    @property
    def callbacks(self) -> List[str]:
        """Get list of callback data in order."""
        return [f"{t.trigger_type}:{t.trigger_data}" for t in self.transitions]
    
    @property
    def back_count(self) -> int:
        """Count of back navigations."""
        return sum(1 for t in self.transitions if t.is_back)
    
    @property
    def back_ratio(self) -> float:
        """Ratio of back navigations to total."""
        if not self.transitions:
            return 0.0
        return self.back_count / len(self.transitions)


@dataclass
class ChainReport:
    """Analysis report with metrics."""
    
    total_transitions: int = 0
    total_sessions: int = 0
    total_users: int = 0
    
    max_depth: int = 0
    avg_depth: float = 0.0
    depth_histogram: Dict[int, int] = field(default_factory=dict)
    
    avg_chain_length: float = 0.0
    max_chain_length: int = 0
    
    all_states: Set[str] = field(default_factory=set)
    visited_states: Set[str] = field(default_factory=set)
    dead_ends: Set[str] = field(default_factory=set)
    orphan_states: Set[str] = field(default_factory=set)
    
    back_usage_ratio: float = 0.0
    total_back_navigations: int = 0
    
    deepest_chains: List[NavigationChain] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_transitions": self.total_transitions,
            "total_sessions": self.total_sessions,
            "total_users": self.total_users,
            "max_depth": self.max_depth,
            "avg_depth": round(self.avg_depth, 2),
            "depth_histogram": self.depth_histogram,
            "avg_chain_length": round(self.avg_chain_length, 2),
            "max_chain_length": self.max_chain_length,
            "all_states": sorted(self.all_states),
            "visited_states": sorted(self.visited_states),
            "dead_ends": sorted(self.dead_ends),
            "orphan_states": sorted(self.orphan_states),
            "back_usage_ratio": round(self.back_usage_ratio, 3),
            "total_back_navigations": self.total_back_navigations,
        }


class ChainAnalyzer:
    """
    Analyzes navigation chains from coverage logs.
    
    Usage:
        analyzer = ChainAnalyzer()
        analyzer.load_csv("coverage.log")
        
        report = analyzer.analyze()
        print(f"Max depth: {report.max_depth}")
        print(f"Dead ends: {report.dead_ends}")
        
        analyzer.export_mermaid("graph.md")
    """
    
    def __init__(self):
        self._transitions: List[TransitionRecord] = []
        self._chains: Dict[str, NavigationChain] = {}
        self._transition_counts: Dict[Tuple[str, str], int] = {}
        self._outgoing: Dict[str, Set[str]] = {}
        self._incoming: Dict[str, Set[str]] = {}
        self._all_states: Set[str] = set()
    
    def load_csv(
        self,
        path: Union[str, Path],
        extended_format: bool = False,
    ) -> "ChainAnalyzer":
        """
        Load transitions from CSV file.
        
        Args:
            path: Path to CSV file
            extended_format: If True, expect extended format with all fields
        """
        path = Path(path)
        if not path.exists():
            return self
        
        session_counter = 0
        
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row or row[0] == "from_state" or row[0] == "timestamp":
                    continue
                
                try:
                    if extended_format or len(row) >= 8:
                        record = TransitionRecord.from_row(row)
                    else:
                        session_id = f"session_{session_counter}"
                        record = TransitionRecord.from_simple_row(row, session_id)
                    
                    self._add_record(record)
                except Exception:
                    continue
        
        return self
    
    def load_records(self, records: List[TransitionRecord]) -> "ChainAnalyzer":
        """Load transitions from a list of records."""
        for record in records:
            self._add_record(record)
        return self
    
    def _add_record(self, record: TransitionRecord) -> None:
        """Add a single transition record."""
        self._transitions.append(record)
        
        if record.session_id not in self._chains:
            self._chains[record.session_id] = NavigationChain(
                session_id=record.session_id,
                user_id=record.user_id,
            )
        self._chains[record.session_id].transitions.append(record)
        
        if record.from_state:
            self._all_states.add(record.from_state)
        if record.to_state:
            self._all_states.add(record.to_state)
        
        if record.from_state and record.to_state:
            key = (record.from_state, record.to_state)
            self._transition_counts[key] = self._transition_counts.get(key, 0) + 1
            
            if record.from_state not in self._outgoing:
                self._outgoing[record.from_state] = set()
            self._outgoing[record.from_state].add(record.to_state)
            
            if record.to_state not in self._incoming:
                self._incoming[record.to_state] = set()
            self._incoming[record.to_state].add(record.from_state)
    
    def analyze(self, initial_state: Optional[str] = None) -> ChainReport:
        """
        Analyze loaded transitions and generate report.
        
        Args:
            initial_state: The initial state (excluded from orphan detection)
        """
        report = ChainReport()
        
        report.total_transitions = len(self._transitions)
        report.total_sessions = len(self._chains)
        report.total_users = len(set(t.user_id for t in self._transitions if t.user_id))
        
        report.all_states = self._all_states.copy()
        report.visited_states = self._all_states.copy()
        
        for state in self._all_states:
            if state not in self._outgoing or not self._outgoing[state]:
                report.dead_ends.add(state)
            
            if state not in self._incoming or not self._incoming[state]:
                if state != initial_state:
                    report.orphan_states.add(state)
        
        if self._transitions:
            depths = [t.depth for t in self._transitions]
            report.max_depth = max(depths) if depths else 0
            report.avg_depth = sum(depths) / len(depths) if depths else 0.0
            
            for d in depths:
                report.depth_histogram[d] = report.depth_histogram.get(d, 0) + 1
        
        if self._chains:
            chain_lengths = [c.length for c in self._chains.values()]
            report.max_chain_length = max(chain_lengths) if chain_lengths else 0
            report.avg_chain_length = sum(chain_lengths) / len(chain_lengths) if chain_lengths else 0.0
        
        if self._transitions:
            back_count = sum(1 for t in self._transitions if t.is_back)
            report.total_back_navigations = back_count
            report.back_usage_ratio = back_count / len(self._transitions)
        
        sorted_chains = sorted(
            self._chains.values(),
            key=lambda c: c.max_depth,
            reverse=True
        )
        report.deepest_chains = sorted_chains[:10]
        
        return report
    
    def get_deepest_chains(self, top: int = 10) -> List[NavigationChain]:
        """Get the chains with deepest navigation."""
        return sorted(
            self._chains.values(),
            key=lambda c: c.max_depth,
            reverse=True
        )[:top]
    
    def get_most_used_transitions(self, top: int = 10) -> List[Tuple[str, str, int]]:
        """Get most frequently used transitions."""
        sorted_transitions = sorted(
            self._transition_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top]
        return [(f, t, c) for (f, t), c in sorted_transitions]
    
    def has_outgoing_transitions(self, state: str) -> bool:
        """Check if a state has any outgoing transitions."""
        return state in self._outgoing and len(self._outgoing[state]) > 0
    
    def export_mermaid(
        self,
        path: Union[str, Path],
        include_counts: bool = True,
        highlight_dead_ends: bool = True,
        highlight_orphans: bool = True,
    ) -> None:
        """
        Export navigation graph as Mermaid diagram.
        
        Args:
            path: Output file path
            include_counts: Include transition counts on edges
            highlight_dead_ends: Highlight dead end states in red
            highlight_orphans: Highlight orphan states in yellow
        """
        lines = ["stateDiagram-v2"]
        
        for state in sorted(self._all_states):
            lines.append(f"    state {state}")
        
        lines.append("")
        
        for (from_state, to_state), count in sorted(self._transition_counts.items()):
            if include_counts and count > 1:
                lines.append(f"    {from_state} --> {to_state} : x{count}")
            else:
                lines.append(f"    {from_state} --> {to_state}")
        
        report = self.analyze()
        
        if highlight_dead_ends and report.dead_ends:
            lines.append("")
            lines.append("    classDef deadEnd fill:#ffcccc,stroke:#cc0000")
            lines.append(f"    class {', '.join(sorted(report.dead_ends))} deadEnd")
        
        if highlight_orphans and report.orphan_states:
            lines.append("")
            lines.append("    classDef orphan fill:#ffffcc,stroke:#cccc00")
            lines.append(f"    class {', '.join(sorted(report.orphan_states))} orphan")
        
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        content = f"# Navigation Chain Graph\n\n```mermaid\n{chr(10).join(lines)}\n```\n"
        
        content += f"\n## Metrics\n\n"
        content += f"- Total transitions: {report.total_transitions}\n"
        content += f"- Max depth: {report.max_depth}\n"
        content += f"- Avg chain length: {report.avg_chain_length:.1f}\n"
        content += f"- Dead ends: {len(report.dead_ends)} ({', '.join(sorted(report.dead_ends)) or 'none'})\n"
        content += f"- Orphans: {len(report.orphan_states)} ({', '.join(sorted(report.orphan_states)) or 'none'})\n"
        content += f"- Back usage: {report.back_usage_ratio:.1%}\n"
        
        path.write_text(content, encoding="utf-8")
    
    def export_json(self, path: Union[str, Path]) -> None:
        """Export analysis report as JSON."""
        import json
        
        report = self.analyze()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
