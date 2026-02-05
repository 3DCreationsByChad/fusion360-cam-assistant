"""
Geometry Helpers for Fusion 360 CAM Assistant.

Provides utility functions for geometry analysis including:
- Tool radius calculation with 80% rule
- Feature accessibility analysis for orientation planning

Exports:
    calculate_minimum_tool_radii: Calculate global and recommended tool radii
    analyze_feature_accessibility: Determine feature reachability per orientation
"""

from typing import Dict, Any, List, Tuple, Optional


def _to_mm_unit(cm_value: float) -> Dict[str, Any]:
    """
    Convert internal cm value to mm with explicit units.

    Fusion 360 API values are internally in cm. This converts to mm
    and returns an explicit unit object per project convention.

    Args:
        cm_value: Value in centimeters from Fusion API

    Returns:
        Dict with {"value": float, "unit": "mm"}
    """
    return {
        "value": round(cm_value * 10, 3),
        "unit": "mm"
    }


def calculate_minimum_tool_radii(body, features: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate minimum tool radius requirements.

    Scans all faces and edges of a body to find the smallest concave radius,
    then applies the 80% rule to recommend a tool radius.

    Per RESEARCH.md Pattern 6:
    - Source: https://www.xometry.com/resources/machining/cnc-machining-optimizing-internal-corner-radii/
    - Tool radius should be <= 80% of smallest internal corner radius

    Args:
        body: BRepBody to analyze
        features: List of detected features (for future per-feature radii)

    Returns:
        {
            "global_minimum_radius": {"value": X, "unit": "mm"} or None,
            "recommended_tool_radius": {"value": X, "unit": "mm"} or None,
            "design_guideline": str
        }
    """
    try:
        import adsk.core
    except ImportError:
        # Running outside Fusion 360
        return {
            "global_minimum_radius": None,
            "recommended_tool_radius": None,
            "design_guideline": "Fusion 360 API not available"
        }

    global_min_radius_mm = float('inf')

    try:
        # Scan all faces for smallest concave radius
        for face in body.faces:
            geom = face.geometry

            # Check toroidal faces (fillets, rounds)
            if isinstance(geom, adsk.core.Torus):
                minor_radius_mm = geom.minorRadius * 10  # cm to mm
                if minor_radius_mm < global_min_radius_mm:
                    global_min_radius_mm = minor_radius_mm

            # Check edges for small arcs
            for edge in face.edges:
                edge_geom = edge.geometry
                if isinstance(edge_geom, (adsk.core.Circle, adsk.core.Arc3D)):
                    radius_mm = edge_geom.radius * 10  # cm to mm
                    if radius_mm < global_min_radius_mm:
                        global_min_radius_mm = radius_mm

    except Exception:
        # If geometry iteration fails, return no radius info
        return {
            "global_minimum_radius": None,
            "recommended_tool_radius": None,
            "design_guideline": "Error analyzing geometry for tool radius"
        }

    # Apply 80% rule: recommended tool radius is 80% of minimum corner
    if global_min_radius_mm != float('inf'):
        recommended_mm = global_min_radius_mm * 0.8
        return {
            "global_minimum_radius": _to_mm_unit(global_min_radius_mm / 10),  # Convert back to cm for _to_mm_unit
            "recommended_tool_radius": _to_mm_unit(recommended_mm / 10),
            "design_guideline": "Tool radius should be <= 80% of smallest internal corner radius"
        }

    return {
        "global_minimum_radius": None,
        "recommended_tool_radius": None,
        "design_guideline": "No internal corners detected; any tool radius acceptable"
    }


def analyze_feature_accessibility(
    features: List[Dict[str, Any]],
    orientation: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Determine which features are reachable in given orientation.

    Per CONTEXT.md decisions:
    - Primary optimization goal: minimize setups/flips
    - Explicitly flag features that are unreachable in any 3-axis orientation

    Per RESEARCH.md Pitfall 6 (Undercut Detection Complexity):
    - Use conservative approach: only flag clearly unreachable features
    - For ambiguous cases, include in reachable list with notes

    This implementation is intentionally simple. More sophisticated analysis
    would check face normals against tool direction, but that requires
    resolving entityTokens to BRepFaces which is session-specific.

    Args:
        features: List of feature dicts from FeatureDetector
        orientation: "Z_UP", "Y_UP", or "X_UP"

    Returns:
        Tuple of (reachable_features, unreachable_features)
        Each feature in unreachable_features includes "unreachable_reason"
    """
    # Tool direction vectors for each orientation (tool approaches from positive direction)
    tool_directions = {
        "Z_UP": (0, 0, -1),   # Tool comes from +Z (standard vertical machining)
        "Y_UP": (0, -1, 0),   # Tool comes from +Y (horizontal machining)
        "X_UP": (-1, 0, 0)    # Tool comes from +X (horizontal machining)
    }
    tool_dir = tool_directions.get(orientation, (0, 0, -1))

    reachable = []
    unreachable = []

    for feature in features:
        # Create a copy to avoid mutating original
        feature_copy = dict(feature)
        feature_copy["orientation"] = orientation

        # Simple heuristic: most features detected by RecognizedHole/RecognizedPocket
        # are accessible from the tool direction they were detected with (Z-down).
        #
        # Per RESEARCH.md Pitfall 6: Use conservative approach.
        # Only flag features that are clearly unreachable:
        # - Features on opposite side of part
        # - Features with normals opposing tool direction by > 90 degrees
        #
        # For now, since we don't have face normal information readily available
        # in the feature dicts, we mark all features as reachable.
        # More sophisticated analysis can be added in future phases.

        # Check if feature has any accessibility hints
        # (e.g., from face normal analysis that could be added to features)
        if feature.get("unreachable_in_3axis", False):
            feature_copy["unreachable_reason"] = feature.get(
                "unreachable_reason",
                "Feature normal opposes tool direction"
            )
            unreachable.append(feature_copy)
        else:
            # Default: assume reachable (conservative per RESEARCH.md)
            reachable.append(feature_copy)

    return reachable, unreachable
