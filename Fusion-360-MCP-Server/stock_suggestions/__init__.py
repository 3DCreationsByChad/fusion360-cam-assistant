"""
Stock Suggestions Module for Fusion 360 CAM Assistant.

This module provides stock dimension calculation and standard size rounding
utilities for CAM setup operations. It helps determine appropriate raw stock
dimensions from part geometry with machining offsets.

Functions:
    calculate_stock_dimensions: Calculate stock from bounding box with offsets
    round_to_standard_size: Round dimension to next standard stock size

Constants:
    DEFAULT_OFFSETS: Default machining offsets (5mm XY, 2.5mm Z)
    METRIC_PLATE_THICKNESSES_MM: Standard metric plate thicknesses
    METRIC_BAR_WIDTHS_MM: Standard metric bar widths
    METRIC_ROUND_DIAMETERS_MM: Standard metric round bar diameters
    IMPERIAL_PLATE_THICKNESSES_IN: Standard imperial plate thicknesses
    IMPERIAL_BAR_WIDTHS_IN: Standard imperial bar widths
    IMPERIAL_ROUND_DIAMETERS_IN: Standard imperial round bar diameters
"""

from .stock_sizes import (
    round_to_standard_size,
    METRIC_PLATE_THICKNESSES_MM,
    METRIC_BAR_WIDTHS_MM,
    METRIC_ROUND_DIAMETERS_MM,
    IMPERIAL_PLATE_THICKNESSES_IN,
    IMPERIAL_BAR_WIDTHS_IN,
    IMPERIAL_ROUND_DIAMETERS_IN,
    MM_PER_INCH
)
from .stock_calculator import calculate_stock_dimensions, DEFAULT_OFFSETS

__all__ = [
    'calculate_stock_dimensions',
    'DEFAULT_OFFSETS',
    'round_to_standard_size',
    'METRIC_PLATE_THICKNESSES_MM',
    'METRIC_BAR_WIDTHS_MM',
    'METRIC_ROUND_DIAMETERS_MM',
    'IMPERIAL_PLATE_THICKNESSES_IN',
    'IMPERIAL_BAR_WIDTHS_IN',
    'IMPERIAL_ROUND_DIAMETERS_IN',
    'MM_PER_INCH'
]
