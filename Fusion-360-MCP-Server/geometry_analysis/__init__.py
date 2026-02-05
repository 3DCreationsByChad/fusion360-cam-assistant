"""
Geometry Analysis Module for Fusion 360 CAM Assistant.

This module provides feature detection and geometry analysis capabilities
using Fusion 360's native RecognizedHole and RecognizedPocket APIs.

Classes:
    FeatureDetector: Detects holes, pockets, slots with confidence scoring
    OrientationAnalyzer: Analyzes orientations and suggests setup sequences

Modules:
    confidence_scorer: Confidence scoring heuristics for feature classification
    geometry_helpers: Tool radius calculation and feature accessibility analysis
    orientation_analyzer: Orientation ranking and setup sequence planning
"""

from .feature_detector import FeatureDetector, DEFAULT_CONFIG
from .confidence_scorer import (
    calculate_confidence,
    needs_review,
    get_ambiguity_flags,
    CONFIDENCE_THRESHOLDS
)
from .orientation_analyzer import OrientationAnalyzer
from .geometry_helpers import calculate_minimum_tool_radii, analyze_feature_accessibility

__all__ = [
    'FeatureDetector',
    'DEFAULT_CONFIG',
    'calculate_confidence',
    'needs_review',
    'get_ambiguity_flags',
    'CONFIDENCE_THRESHOLDS',
    'OrientationAnalyzer',
    'calculate_minimum_tool_radii',
    'analyze_feature_accessibility'
]
