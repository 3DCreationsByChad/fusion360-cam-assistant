"""
Stock Sizes Module for Fusion 360 CAM Assistant.

This module provides standard stock size tables for metric and imperial
unit systems. These tables represent commonly available stock dimensions
from material suppliers.

Functions:
    round_to_standard_size: Round a dimension up to the next available standard size

Constants:
    METRIC_PLATE_THICKNESSES_MM: Standard metric plate thicknesses
    METRIC_BAR_WIDTHS_MM: Standard metric bar/flat stock widths
    METRIC_ROUND_DIAMETERS_MM: Standard metric round bar diameters
    IMPERIAL_PLATE_THICKNESSES_IN: Standard imperial plate thicknesses
    IMPERIAL_BAR_WIDTHS_IN: Standard imperial bar/flat stock widths
    IMPERIAL_ROUND_DIAMETERS_IN: Standard imperial round bar diameters
"""

from typing import Literal

# Metric standard sizes (in mm)

METRIC_PLATE_THICKNESSES_MM = [
    3, 4, 5, 6, 8, 10, 12, 15, 16, 18, 20, 22, 25,
    30, 32, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 90, 100
]

METRIC_BAR_WIDTHS_MM = [
    10, 12, 15, 16, 18, 20, 22, 25, 30, 32, 35, 40, 45, 50,
    55, 60, 65, 70, 75, 80, 90, 100, 110, 120, 130, 140, 150,
    160, 180, 200, 220, 250, 300
]

METRIC_ROUND_DIAMETERS_MM = [
    6, 8, 10, 12, 14, 15, 16, 18, 20, 22, 25, 28, 30, 32,
    35, 38, 40, 42, 45, 48, 50, 55, 60, 65, 70, 75, 80, 85,
    90, 95, 100, 110, 120, 130, 150
]

# Imperial standard sizes (in inches)

IMPERIAL_PLATE_THICKNESSES_IN = [
    0.125, 0.1875, 0.25, 0.3125, 0.375, 0.4375, 0.5,
    0.625, 0.75, 0.875, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 3.5, 4.0
]

IMPERIAL_BAR_WIDTHS_IN = [
    0.5, 0.625, 0.75, 0.875, 1.0, 1.125, 1.25, 1.375, 1.5, 1.75,
    2.0, 2.25, 2.5, 2.75, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0,
    7.0, 8.0, 9.0, 10.0, 12.0
]

IMPERIAL_ROUND_DIAMETERS_IN = [
    0.25, 0.3125, 0.375, 0.4375, 0.5, 0.5625, 0.625, 0.75, 0.875,
    1.0, 1.125, 1.25, 1.375, 1.5, 1.625, 1.75, 2.0, 2.25, 2.5,
    2.75, 3.0, 3.5, 4.0
]

# Conversion constant
MM_PER_INCH = 25.4


def round_to_standard_size(
    dimension_mm: float,
    unit_system: Literal["metric", "imperial"],
    dimension_type: Literal["width", "thickness", "round_diameter"]
) -> float:
    """
    Round a dimension up to the next available standard stock size.

    This function finds the smallest standard size that is >= the input dimension.
    For imperial unit system, the dimension (in mm) is converted to inches,
    rounded to standard imperial sizes, then converted back to mm.

    Args:
        dimension_mm: The dimension to round, in millimeters
        unit_system: "metric" or "imperial" - determines which size table to use
        dimension_type: Type of dimension:
            - "width": For bar/flat stock width or depth dimensions
            - "thickness": For plate thickness (typically height/Z dimension)
            - "round_diameter": For round bar stock diameter

    Returns:
        The next larger standard size in millimeters.
        If the input exceeds all standard sizes, returns the largest available.

    Examples:
        >>> round_to_standard_size(45.5, "metric", "width")
        50.0  # Next larger metric bar width

        >>> round_to_standard_size(27.0, "imperial", "width")
        28.575  # 1.125" in mm (next larger imperial bar width)

        >>> round_to_standard_size(7.5, "metric", "thickness")
        8.0  # Next larger metric plate thickness
    """
    if unit_system == "metric":
        # Use metric tables directly (values already in mm)
        if dimension_type == "thickness":
            sizes = METRIC_PLATE_THICKNESSES_MM
        elif dimension_type == "round_diameter":
            sizes = METRIC_ROUND_DIAMETERS_MM
        else:  # "width" - covers width/depth
            sizes = METRIC_BAR_WIDTHS_MM

        # Find next larger size
        for size in sizes:
            if size >= dimension_mm:
                return float(size)
        # If all sizes are smaller, return largest
        return float(sizes[-1])

    else:  # imperial
        # Convert mm to inches for comparison
        dimension_in = dimension_mm / MM_PER_INCH

        if dimension_type == "thickness":
            sizes = IMPERIAL_PLATE_THICKNESSES_IN
        elif dimension_type == "round_diameter":
            sizes = IMPERIAL_ROUND_DIAMETERS_IN
        else:  # "width"
            sizes = IMPERIAL_BAR_WIDTHS_IN

        # Find next larger size in inches
        result_in = None
        for size in sizes:
            if size >= dimension_in:
                result_in = size
                break

        # If all sizes are smaller, use largest
        if result_in is None:
            result_in = sizes[-1]

        # Convert back to mm
        return result_in * MM_PER_INCH
