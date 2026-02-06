"""Toolpath strategy rules engine for CNC machining.

This module provides the core intelligence for Phase 4 toolpath suggestions.
It contains pure-Python modules that encode CNC machining heuristics to map
detected features to recommended CAM operations with calculated cutting parameters.

No Fusion API dependency - these are testable calculation modules.

Components:
- material_library: Material property database with SFM and chip load values
- feeds_speeds: RPM and feed rate calculation from material + tool geometry
- tool_selector: Tool selection logic with 80% corner radius rule
- operation_mapper: Feature-to-operation mapping with condition evaluation
"""

# Import all modules
from .material_library import MATERIAL_LIBRARY, get_material_properties
from .feeds_speeds import calculate_feeds_speeds
from .tool_selector import select_best_tool
from .operation_mapper import map_feature_to_operations, OPERATION_RULES
from .strategy_preferences import (
    get_strategy_preference,
    save_strategy_preference,
    initialize_strategy_schema,
    STRATEGY_PREFERENCES_SCHEMA
)

# Export all public APIs
__all__ = [
    # Material library
    "MATERIAL_LIBRARY",
    "get_material_properties",
    # Feeds and speeds
    "calculate_feeds_speeds",
    # Tool selector
    "select_best_tool",
    # Operation mapper
    "map_feature_to_operations",
    "OPERATION_RULES",
    # Strategy preferences
    "get_strategy_preference",
    "save_strategy_preference",
    "initialize_strategy_schema",
    "STRATEGY_PREFERENCES_SCHEMA"
]
