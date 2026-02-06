"""Feeds and speeds calculation for CNC machining.

Calculates RPM, feed rates, stepover, and stepdown based on
material properties and tool geometry.
"""

from .material_library import get_material_properties


def calculate_feeds_speeds(
    material: str,
    tool: dict,
    is_carbide: bool = True,
    operation_type: str = "roughing"
) -> dict:
    """Calculate cutting parameters for a tool and material combination.

    Uses industry-standard formulas:
    - RPM = (SFM * 3.82) / diameter_inches
    - Feed rate = RPM * flutes * chip_load

    Args:
        material: Material name (passed to get_material_properties)
        tool: Tool dict with keys:
            - diameter: {"value": X, "unit": "mm"}
            - flutes: int (number of cutting edges)
            - flute_length (optional): {"value": X, "unit": "mm"}
        is_carbide: True for carbide tooling, False for HSS (affects SFM)
        operation_type: "roughing" or "finishing" (affects chip load and stepover)

    Returns:
        dict with calculated parameters in explicit unit format:
        {
            "rpm": {"value": int, "unit": "rpm"},
            "feed_rate": {"value": int, "unit": "mm/min"},
            "stepover_roughing": {"value": float, "unit": "mm"},
            "stepover_finishing": {"value": float, "unit": "mm"},
            "stepdown_roughing": {"value": float, "unit": "mm"},
            "calculation_basis": str,
            "is_carbide": bool
        }
    """
    # Get material properties
    mat_props = get_material_properties(material)

    # Select SFM based on tool material
    sfm = mat_props["sfm_carbide"] if is_carbide else mat_props["sfm_hss"]

    # Extract tool diameter and convert to inches
    diameter_mm = tool["diameter"]["value"]
    diameter_inches = diameter_mm / 25.4

    # Calculate RPM using industry formula
    rpm_calculated = (sfm * 3.82) / diameter_inches
    # Cap at typical spindle maximum
    rpm = min(rpm_calculated, 24000)

    # Select chip load based on operation type
    chip_load_min, chip_load_max = mat_props["chip_load_range"]
    if operation_type == "finishing":
        # Use 70% of minimum for light finishing cuts
        chip_load = chip_load_min * 0.7
    else:  # roughing
        # Use midpoint of range for balanced roughing
        chip_load = (chip_load_min + chip_load_max) / 2

    # Get number of flutes
    flutes = tool.get("flutes", 2)  # Default to 2 if not specified

    # Calculate feed rate in inches per minute
    feed_rate_ipm = rpm * flutes * chip_load
    # Convert to mm per minute
    feed_rate_mmpm = feed_rate_ipm * 25.4

    # Calculate stepover values (percentage of tool diameter)
    # Roughing: 40-50% (use 45% midpoint)
    stepover_roughing = diameter_mm * 0.45
    # Finishing: 10-20% (use 15% midpoint)
    stepover_finishing = diameter_mm * 0.15

    # Calculate stepdown for roughing (0.5-1.5x diameter, use 1.0x midpoint)
    stepdown_roughing = diameter_mm * 1.0

    # Build calculation basis string
    tool_material = "carbide" if is_carbide else "HSS"
    calculation_basis = (
        f"Material: {material}, SFM: {sfm}, "
        f"Tool: {diameter_mm:.2f}mm {tool_material} {flutes}-flute, "
        f"Operation: {operation_type}"
    )

    return {
        "rpm": {"value": round(rpm), "unit": "rpm"},
        "feed_rate": {"value": round(feed_rate_mmpm), "unit": "mm/min"},
        "stepover_roughing": {"value": round(stepover_roughing, 2), "unit": "mm"},
        "stepover_finishing": {"value": round(stepover_finishing, 2), "unit": "mm"},
        "stepdown_roughing": {"value": round(stepdown_roughing, 2), "unit": "mm"},
        "calculation_basis": calculation_basis,
        "is_carbide": is_carbide
    }
