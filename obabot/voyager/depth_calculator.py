"""
Depth calculator for navigation tracking.

Determines the navigation depth based on callback data patterns.
"""

from __future__ import annotations

import re
from typing import List, Optional, Set


class DepthCalculator:
    """
    Calculates navigation depth based on callback patterns.
    
    Depth rules:
    - Main menu = 0
    - Role selection = 1
    - Back navigation = depth - 1
    - Other transitions = depth + 1
    
    Usage:
        calc = DepthCalculator()
        calc.add_main_menu_pattern("nav:main", "nv:main", "employee:menu")
        calc.add_back_pattern("nav:back", ":back:", "back:")
        calc.add_role_pattern("cr:", "choose_role:")
        
        depth = calc.calculate(current_depth=2, callback_data="nav:back")
        # Returns 1
    """
    
    def __init__(self):
        self._main_menu_exact: Set[str] = {"nav:main", "nv:main", "employee:menu"}
        self._back_exact: Set[str] = {"nav:back", "callback:back", "callback:nav:back"}
        self._back_contains: List[str] = [":back:", "_back_", ".back."]
        self._back_ends: List[str] = [":back", "_back"]
        self._role_prefixes: List[str] = ["cr:", "choose_role:"]
        self._reset_patterns: List[str] = []
    
    def add_main_menu_pattern(self, *patterns: str) -> "DepthCalculator":
        """Add exact patterns that reset depth to 0."""
        self._main_menu_exact.update(patterns)
        return self
    
    def add_back_pattern(self, *patterns: str) -> "DepthCalculator":
        """Add patterns that indicate back navigation."""
        for p in patterns:
            if p.startswith(":") or p.endswith(":"):
                self._back_contains.append(p)
            else:
                self._back_exact.add(p)
        return self
    
    def add_role_pattern(self, *prefixes: str) -> "DepthCalculator":
        """Add prefixes that indicate role selection (depth=1)."""
        self._role_prefixes.extend(prefixes)
        return self
    
    def add_reset_pattern(self, *patterns: str) -> "DepthCalculator":
        """Add patterns that reset depth to 0 (substring match)."""
        self._reset_patterns.extend(patterns)
        return self
    
    def is_main_menu(self, callback_data: str) -> bool:
        """Check if callback leads to main menu."""
        if callback_data in self._main_menu_exact:
            return True
        return any(p in callback_data for p in self._reset_patterns)
    
    def is_back_navigation(self, callback_data: str) -> bool:
        """Check if callback is back navigation."""
        if callback_data in self._back_exact:
            return True
        if any(p in callback_data for p in self._back_contains):
            return True
        if any(callback_data.endswith(p) for p in self._back_ends):
            return True
        return False
    
    def is_role_selection(self, callback_data: str) -> bool:
        """Check if callback is role selection."""
        return any(callback_data.startswith(p) for p in self._role_prefixes)
    
    def calculate(
        self,
        current_depth: int,
        callback_data: str,
        *,
        from_state: Optional[str] = None,
        to_state: Optional[str] = None,
    ) -> int:
        """
        Calculate new depth after a transition.
        
        Args:
            current_depth: Current navigation depth
            callback_data: The callback data triggering the transition
            from_state: Source state (optional, for state-based rules)
            to_state: Target state (optional, for state-based rules)
        
        Returns:
            New depth value (minimum 0)
        """
        if self.is_main_menu(callback_data):
            return 0
        
        if self.is_back_navigation(callback_data):
            return max(0, current_depth - 1)
        
        if self.is_role_selection(callback_data):
            return 1
        
        return current_depth + 1
    
    def detect_is_back(self, callback_data: str, depth_before: int, depth_after: int) -> bool:
        """
        Detect if a transition is a back navigation.
        
        Uses both pattern matching and depth comparison.
        """
        if self.is_back_navigation(callback_data):
            return True
        if self.is_main_menu(callback_data):
            return depth_before > 0
        return depth_after < depth_before
