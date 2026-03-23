"""
FSM Voyager integration for obabot.

Provides chain tracking, depth analysis, coverage visualization,
and **FSM model extraction** from registered handlers.

For full fsm-voyager integration, install: pip install fsm-voyager
Then use the bridge module:
    from obabot.voyager.bridge import quick_coverage_report

To extract model.json from handler registrations:
    from obabot.voyager import extract_fsm_model
    model = extract_fsm_model(router, bot_name="MyBot", save_to="model.json")
"""

from obabot.voyager.chain_analyzer import ChainAnalyzer, ChainReport, NavigationChain
from obabot.voyager.depth_calculator import DepthCalculator
from obabot.voyager.extractor import extract_fsm_model
from obabot.voyager.tracker import ChainTracker
from obabot.voyager.bridge import is_fsm_voyager_available

__all__ = [
    "ChainAnalyzer",
    "ChainReport",
    "NavigationChain",
    "DepthCalculator",
    "ChainTracker",
    "extract_fsm_model",
    "is_fsm_voyager_available",
]
