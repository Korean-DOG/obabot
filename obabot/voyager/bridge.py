"""
Bridge module for fsm-voyager integration.

Provides utilities to connect obabot coverage logs with fsm-voyager analysis tools.
Requires fsm-voyager to be installed: pip install fsm-voyager
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional, Set, Tuple, Union

if TYPE_CHECKING:
    from fsm_voyager import FSMModel, CoverageStats


def _check_fsm_voyager() -> None:
    """Check if fsm-voyager is installed."""
    try:
        import fsm_voyager  # noqa: F401
    except ImportError:
        raise ImportError(
            "fsm-voyager is required for this feature. "
            "Install it with: pip install fsm-voyager"
        )


def load_model(path: Union[str, Path]) -> "FSMModel":
    """
    Load FSM model from JSON file using fsm-voyager.
    
    Args:
        path: Path to model.json file
    
    Returns:
        FSMModel instance
    
    Raises:
        ImportError: If fsm-voyager is not installed
        FileNotFoundError: If model file doesn't exist
    """
    _check_fsm_voyager()
    from fsm_voyager import load_model as _load_model
    return _load_model(path)


def parse_coverage_logs(
    logs_dir: Union[str, Path],
    file_pattern: str = "*.log",
) -> Set[Tuple[str, str, str]]:
    """
    Parse coverage logs using fsm-voyager.
    
    Args:
        logs_dir: Directory containing log files
        file_pattern: Glob pattern for log files
    
    Returns:
        Set of (from_state, to_state, action) tuples
    
    Raises:
        ImportError: If fsm-voyager is not installed
    """
    _check_fsm_voyager()
    from fsm_voyager import parse_coverage_logs as _parse_coverage_logs
    return _parse_coverage_logs(logs_dir, file_pattern)


def calculate_coverage(
    model: "FSMModel",
    covered_transitions: Set[Tuple[str, str, str]],
) -> "CoverageStats":
    """
    Calculate coverage statistics using fsm-voyager.
    
    Args:
        model: FSM model
        covered_transitions: Set of covered transitions
    
    Returns:
        CoverageStats with coverage metrics
    
    Raises:
        ImportError: If fsm-voyager is not installed
    """
    _check_fsm_voyager()
    from fsm_voyager.coverage_report import calculate_coverage as _calculate_coverage
    return _calculate_coverage(model, covered_transitions)


def generate_coverage_report(
    model: "FSMModel",
    stats: "CoverageStats",
    show_buttons: bool = True,
    show_text: bool = True,
) -> str:
    """
    Generate Markdown coverage report using fsm-voyager.
    
    Args:
        model: FSM model
        stats: Coverage statistics
        show_buttons: Include buttons in diagram
        show_text: Include text in diagram
    
    Returns:
        Markdown report string
    
    Raises:
        ImportError: If fsm-voyager is not installed
    """
    _check_fsm_voyager()
    from fsm_voyager import generate_coverage_report as _generate_coverage_report
    return _generate_coverage_report(model, stats, show_buttons, show_text)


def generate_mermaid_diagram(
    model: "FSMModel",
    stats: Optional["CoverageStats"] = None,
    show_buttons: bool = True,
    show_text: bool = True,
) -> str:
    """
    Generate Mermaid diagram using fsm-voyager.
    
    Args:
        model: FSM model
        stats: Coverage statistics (None = no highlighting)
        show_buttons: Include buttons in diagram
        show_text: Include text in diagram
    
    Returns:
        Mermaid diagram string
    
    Raises:
        ImportError: If fsm-voyager is not installed
    """
    _check_fsm_voyager()
    from fsm_voyager import generate_mermaid_diagram as _generate_mermaid_diagram
    return _generate_mermaid_diagram(model, stats, show_buttons, show_text)


def generate_graphviz_diagram(
    model: "FSMModel",
    stats: Optional["CoverageStats"] = None,
    show_buttons: bool = True,
    show_text: bool = True,
) -> str:
    """
    Generate Graphviz DOT diagram using fsm-voyager.
    
    Creates Telegram-like state cards with message text and buttons.
    
    Args:
        model: FSM model
        stats: Coverage statistics (None = no highlighting)
        show_buttons: Include buttons in diagram
        show_text: Include text in diagram
    
    Returns:
        DOT-language string
    
    Raises:
        ImportError: If fsm-voyager is not installed
    """
    _check_fsm_voyager()
    from fsm_voyager import generate_graphviz_diagram as _generate_graphviz_diagram
    return _generate_graphviz_diagram(model, stats, show_buttons, show_text)


def quick_coverage_report(
    model_path: Union[str, Path],
    logs_dir: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    format: str = "md",
) -> str:
    """
    Quick one-liner to generate coverage report.
    
    Args:
        model_path: Path to model.json
        logs_dir: Directory with coverage logs
        output_path: Optional output file path
        format: Output format ("md" for Markdown, "dot" for Graphviz)
    
    Returns:
        Report content string
    
    Example:
        from obabot.voyager.bridge import quick_coverage_report
        
        report = quick_coverage_report(
            "model.json",
            "./coverage-logs",
            "coverage_report.md"
        )
    """
    _check_fsm_voyager()
    
    model = load_model(model_path)
    covered = parse_coverage_logs(logs_dir)
    stats = calculate_coverage(model, covered)
    
    if format == "dot":
        content = generate_graphviz_diagram(model, stats)
    else:
        content = generate_coverage_report(model, stats)
    
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
    
    return content


def is_fsm_voyager_available() -> bool:
    """Check if fsm-voyager is installed and available."""
    try:
        import fsm_voyager  # noqa: F401
        return True
    except ImportError:
        return False
