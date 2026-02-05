"""
Geometry Analysis Module for Fusion 360 CAM Assistant.

This module provides feature detection and geometry analysis capabilities
using Fusion 360's native RecognizedHole and RecognizedPocket APIs.

Classes:
    FeatureDetector: Detects holes, pockets, slots with confidence scoring

Modules:
    confidence_scorer: Confidence scoring heuristics for feature classification
"""

from .feature_detector import FeatureDetector, DEFAULT_CONFIG
from .confidence_scorer import (
    calculate_confidence,
    needs_review,
    get_ambiguity_flags,
    CONFIDENCE_THRESHOLDS
)

__all__ = [
    'FeatureDetector',
    'DEFAULT_CONFIG',
    'calculate_confidence',
    'needs_review',
    'get_ambiguity_flags',
    'CONFIDENCE_THRESHOLDS'
]
