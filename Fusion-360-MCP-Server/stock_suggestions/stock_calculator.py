"""
Stock Calculator Module for Fusion 360 CAM Assistant.

This module provides stock dimension calculation from bounding box geometry,
applying configurable machining offsets and rounding to standard stock sizes.

Functions:
    calculate_stock_dimensions: Calculate stock from bounding box with offsets

Constants:
    DEFAULT_OFFSETS: Default machining offsets (5mm XY, 2.5mm Z per side)
"""

from typing import Dict, Any, Optional, Literal
from .stock_sizes import round_to_standard_size

# Default machining offsets per CONTEXT.md
# XY offset is applied to all 4 sides (2x per axis)
# Z offset is applied to top only (single side)
DEFAULT_OFFSETS = {
    "xy_mm": 5.0,   # 5mm XY offset per side (applied to all 4 sides)
    "z_mm": 2.5     # 2.5mm Z offset (top only)
}


def calculate_stock_dimensions(
    bbox: Any,
    offsets: Optional[Dict[str, float]] = None,
    round_to_standard: bool = True,
    unit_system: Literal["metric", "imperial"] = "metric"
) -> Dict[str, Any]:
    """
    Calculate stock dimensions from a Fusion 360 bounding box.

    This function extracts dimensions from a BoundingBox3D, applies machining
    offsets, and optionally rounds to standard stock sizes.

    Offset Application:
        - XY offset: Applied to ALL 4 sides. For a dimension like width,
          the total offset is 2 * xy_mm (one per side).
        - Z offset: Applied to TOP ONLY. The height gains only z_mm
          (assumes bottom face is reference/fixture surface).

    Args:
        bbox: adsk.core.BoundingBox3D from body.boundingBox
              Contains minPoint and maxPoint with x/y/z coordinates in cm
        offsets: Optional dict with "xy_mm" and "z_mm" keys.
                 Defaults to DEFAULT_OFFSETS (5mm XY, 2.5mm Z).
        round_to_standard: If True, round dimensions to standard stock sizes.
                           Defaults to True.
        unit_system: "metric" or "imperial" for standard size tables.
                     Defaults to "metric".

    Returns:
        Dict containing:
            - width: {"value": X, "unit": "mm"} - X dimension with offsets
            - depth: {"value": Y, "unit": "mm"} - Y dimension with offsets
            - height: {"value": Z, "unit": "mm"} - Z dimension with offset
            - raw_dimensions: {"width": raw_x, "depth": raw_y, "height": raw_z}
                              Original dimensions before offsets (in mm)
            - offsets_applied: The offset values used
            - rounded_to_standard: Boolean indicating if rounding was applied
            - unit_system: The unit system used for rounding

    Example:
        >>> bbox = body.boundingBox
        >>> result = calculate_stock_dimensions(bbox)
        >>> print(result["width"])
        {"value": 50.0, "unit": "mm"}

    Notes:
        - Fusion 360 API returns coordinates in centimeters, this function
          converts to millimeters internally (* 10)
        - Width/depth use "width" rounding category (bar/flat stock)
        - Height uses "thickness" rounding category (plate stock)
    """
    # Use default offsets if not provided
    if offsets is None:
        offsets = DEFAULT_OFFSETS.copy()

    # Extract offset values
    xy_offset = offsets.get("xy_mm", DEFAULT_OFFSETS["xy_mm"])
    z_offset = offsets.get("z_mm", DEFAULT_OFFSETS["z_mm"])

    # Extract raw dimensions from bounding box
    # Fusion 360 API uses centimeters, convert to millimeters (* 10)
    raw_width = (bbox.maxPoint.x - bbox.minPoint.x) * 10  # X dimension in mm
    raw_depth = (bbox.maxPoint.y - bbox.minPoint.y) * 10  # Y dimension in mm
    raw_height = (bbox.maxPoint.z - bbox.minPoint.z) * 10  # Z dimension in mm

    # Apply offsets
    # XY: Applied to all 4 sides (2x per axis for width/depth)
    # Z: Applied to top only (1x for height)
    width_with_offset = raw_width + (2 * xy_offset)
    depth_with_offset = raw_depth + (2 * xy_offset)
    height_with_offset = raw_height + z_offset

    # Round to standard sizes if requested
    if round_to_standard:
        final_width = round_to_standard_size(width_with_offset, unit_system, "width")
        final_depth = round_to_standard_size(depth_with_offset, unit_system, "width")
        final_height = round_to_standard_size(height_with_offset, unit_system, "thickness")
    else:
        final_width = width_with_offset
        final_depth = depth_with_offset
        final_height = height_with_offset

    return {
        "width": {"value": final_width, "unit": "mm"},
        "depth": {"value": final_depth, "unit": "mm"},
        "height": {"value": final_height, "unit": "mm"},
        "raw_dimensions": {
            "width": raw_width,
            "depth": raw_depth,
            "height": raw_height
        },
        "offsets_applied": {
            "xy_mm": xy_offset,
            "z_mm": z_offset
        },
        "rounded_to_standard": round_to_standard,
        "unit_system": unit_system
    }
