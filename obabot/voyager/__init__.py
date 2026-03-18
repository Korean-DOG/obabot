"""
FSM Voyager integration for obabot.

Provides chain tracking, depth analysis, and coverage visualization.

For full fsm-voyager integration, install: pip install fsm-voyager
Then use the bridge module:
    from obabot.voyager.bridge import quick_coverage_report
"""

from obabot.voyager.chain_analyzer import ChainAnalyzer, ChainReport, NavigationChain
from obabot.voyager.depth_calculator import DepthCalculator
from obabot.voyager.tracker import ChainTracker
from obabot.voyager.bridge import is_fsm_voyager_available

__all__ = [
    "ChainAnalyzer",
    "ChainReport", 
    "NavigationChain",
    "DepthCalculator",
    "ChainTracker",
    "is_fsm_voyager_available",
]
