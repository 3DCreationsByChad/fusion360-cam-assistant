"""Tool selection logic for CNC machining.

Selects the largest tool that fits feature constraints using the
80% corner radius rule and flute length requirements.
"""


def select_best_tool(
    feature: dict,
    available_tools: list,
    tool_type_filter: str = None
) -> dict:
    """Select the best fitting tool for a feature.

    Uses the 80% rule: tool_radius <= 0.8 * min_corner_radius
    Also enforces flute length constraint: flute_length >= depth * 1.2 (20% safety margin)

    Args:
        feature: Feature dict with keys:
            - min_corner_radius: {"value": X, "unit": "mm"} (preferred)
            - min_internal_radius_mm: float (Phase 2 fallback format)
            - depth: {"value": X, "unit": "mm"} (optional, for depth checking)
        available_tools: List of tool dicts, each with:
            - diameter: {"value": X, "unit": "mm"}
            - type: str (e.g., "flat_endmill", "ball_endmill")
            - flute_length: {"value": X, "unit": "mm"} (optional)
            - flutes: int (optional)
        tool_type_filter: Optional type filter (e.g., "endmill", "drill")

    Returns:
        dict with either:
        - Success: {"status": "ok", "tool": selected_tool, "reasoning": str,
                    "stepover_roughing": {...}, "stepover_finishing": {...}}
        - Failure: {"status": "no_tool_available", "reason": str,
                    "constraint": {"max_radius_mm": float}}
    """
    # Extract minimum corner radius from feature
    # Try preferred format first
    min_radius = feature.get("min_corner_radius", {}).get("value", None)

    # Fallback to Phase 2 format
    if min_radius is None:
        min_radius = feature.get("min_internal_radius_mm", float('inf'))

    # If still no radius constraint, use large value (no corner constraint)
    if min_radius is None or min_radius == 0:
        min_radius = float('inf')

    # Apply 80% rule for tool radius constraint
    max_tool_radius = min_radius * 0.8

    # Extract feature depth if present
    feature_depth = feature.get("depth", {}).get("value", None)
    if feature_depth is None:
        # Try Phase 2 format
        feature_depth = feature.get("depth_mm", None)

    # Start with all available tools
    fitting_tools = available_tools.copy()

    # Filter by tool type if specified
    if tool_type_filter:
        filter_lower = tool_type_filter.lower()
        fitting_tools = [
            t for t in fitting_tools
            if filter_lower in t.get("type", "").lower()
        ]

    # Filter by radius constraint (80% rule)
    fitting_tools = [
        t for t in fitting_tools
        if (t["diameter"]["value"] / 2) <= max_tool_radius
    ]

    # Filter by flute length if depth is specified
    if feature_depth is not None:
        required_flute_length = feature_depth * 1.2  # 20% safety margin
        fitting_tools = [
            t for t in fitting_tools
            if t.get("flute_length", {}).get("value", float('inf')) >= required_flute_length
        ]

    # Check if any tools fit
    if not fitting_tools:
        reason_parts = []
        if tool_type_filter:
            reason_parts.append(f"type='{tool_type_filter}'")
        if min_radius != float('inf'):
            reason_parts.append(f"max_radius={max_tool_radius:.2f}mm (80% of {min_radius:.2f}mm)")
        if feature_depth is not None:
            reason_parts.append(f"min_flute_length={feature_depth * 1.2:.2f}mm (depth {feature_depth:.2f}mm * 1.2)")

        reason = "No tools available matching constraints: " + ", ".join(reason_parts)

        return {
            "status": "no_tool_available",
            "reason": reason,
            "constraint": {
                "max_radius_mm": max_tool_radius if max_tool_radius != float('inf') else None,
                "min_flute_length_mm": feature_depth * 1.2 if feature_depth else None
            }
        }

    # Select largest fitting tool (maximizes material removal rate)
    selected_tool = max(fitting_tools, key=lambda t: t["diameter"]["value"])

    # Calculate stepover values for this tool
    tool_diameter = selected_tool["diameter"]["value"]
    stepover_roughing = round(tool_diameter * 0.45, 2)  # 45% for roughing
    stepover_finishing = round(tool_diameter * 0.15, 2)  # 15% for finishing

    # Build reasoning string
    reasoning_parts = [
        f"Selected {tool_diameter:.2f}mm {selected_tool.get('type', 'tool')}",
        f"(largest fitting tool, radius {tool_diameter/2:.2f}mm <= {max_tool_radius:.2f}mm limit)"
    ]

    if feature_depth is not None:
        flute_length = selected_tool.get("flute_length", {}).get("value", "unknown")
        reasoning_parts.append(
            f"flute length {flute_length}mm >= {feature_depth * 1.2:.2f}mm required"
        )

    if tool_type_filter:
        reasoning_parts.append(f"matches type filter '{tool_type_filter}'")

    reasoning = ". ".join(reasoning_parts) + "."

    return {
        "status": "ok",
        "tool": selected_tool,
        "reasoning": reasoning,
        "stepover_roughing": {"value": stepover_roughing, "unit": "mm"},
        "stepover_finishing": {"value": stepover_finishing, "unit": "mm"}
    }
