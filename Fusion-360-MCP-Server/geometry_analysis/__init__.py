"""
Geometry Analysis Module for Fusion 360 CAM Assistant.

This module provides feature detection and geometry analysis capabilities
using Fusion 360's native RecognizedHole and RecognizedPocket APIs.

Classes:
    FeatureDetector: Detects holes, pockets, and other CAM-relevant features
"""

from .feature_detector import FeatureDetector

__all__ = ['FeatureDetector']
