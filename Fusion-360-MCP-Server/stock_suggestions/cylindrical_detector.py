"""
Cylindrical Part Detector for Fusion 360 CAM Assistant.

Detects when parts are suitable for round stock (lathe candidates) based on
bounding box analysis and face geometry. Returns confidence score, reasoning,
and enclosing diameter for round stock sizing.

Per CONTEXT.md: For cylindrical parts, show both round and rectangular stock
options with trade-offs.
"""

import math
from typing import Dict, Any, Optional, List

# Fusion 360 imports - available when running inside Fusion
try:
    import adsk.core
    import adsk.fusion
    FUSION_AVAILABLE = True
except ImportError:
    FUSION_AVAILABLE = False


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_CONFIG = {
    # Tolerance for comparing dimensions (20% = dimensions within 20% are "similar")
    "dimension_similarity_tolerance": 0.20,
    # Minimum ratio for elongated detection (longest / cross-section)
    "elongated_min_ratio": 1.5,
    # Weight for face analysis in scoring
    "face_score_weight": 0.6,
    # Weight for bounding box shape analysis in scoring
    "bbox_score_weight": 0.4,
    # Minimum confidence to consider cylindrical
    "cylindrical_threshold": 0.5
}


def _to_mm(cm_value: float) -> float:
    """Convert Fusion API centimeter value to millimeters."""
    return cm_value * 10.0


def _get_bounding_box_dimensions(body) -> Optional[Dict[str, float]]:
    """
    Extract bounding box dimensions from a BRepBody.

    Args:
        body: BRepBody to analyze

    Returns:
        Dict with x_mm, y_mm, z_mm dimensions, or None if unavailable
    """
    if not FUSION_AVAILABLE:
        return None

    try:
        bbox = body.boundingBox
        if bbox is None:
            return None

        # Get dimensions in mm (API returns cm)
        x_mm = _to_mm(bbox.maxPoint.x - bbox.minPoint.x)
        y_mm = _to_mm(bbox.maxPoint.y - bbox.minPoint.y)
        z_mm = _to_mm(bbox.maxPoint.z - bbox.minPoint.z)

        return {
            "x_mm": round(x_mm, 3),
            "y_mm": round(y_mm, 3),
            "z_mm": round(z_mm, 3)
        }
    except Exception:
        return None


def _count_cylindrical_faces(body) -> tuple:
    """
    Count cylindrical faces vs total faces on a body.

    Returns:
        Tuple of (cylindrical_count, total_count)
    """
    if not FUSION_AVAILABLE:
        return (0, 0)

    try:
        faces = body.faces
        if faces is None:
            return (0, 0)

        total_count = faces.count
        cylindrical_count = 0

        for face in faces:
            try:
                geometry = face.geometry
                if geometry is not None:
                    # Check if face geometry is a Cylinder
                    if hasattr(adsk.core, 'Cylinder') and isinstance(geometry, adsk.core.Cylinder):
                        cylindrical_count += 1
            except Exception:
                continue

        return (cylindrical_count, total_count)
    except Exception:
        return (0, 0)


def _analyze_bounding_box_shape(dimensions: Dict[str, float], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze bounding box dimensions to detect elongated or disc shapes.

    Args:
        dimensions: Dict with x_mm, y_mm, z_mm
        config: Configuration dict

    Returns:
        Dict with shape analysis results
    """
    tolerance = config.get("dimension_similarity_tolerance", 0.20)
    elongated_ratio = config.get("elongated_min_ratio", 1.5)

    # Sort dimensions to find shape characteristics
    dims = [dimensions["x_mm"], dimensions["y_mm"], dimensions["z_mm"]]
    sorted_dims = sorted(dims)

    min_dim = sorted_dims[0]
    mid_dim = sorted_dims[1]
    max_dim = sorted_dims[2]

    # Find which axis corresponds to each dimension
    axis_map = {dimensions["x_mm"]: "X", dimensions["y_mm"]: "Y", dimensions["z_mm"]: "Z"}
    max_axis = axis_map.get(max_dim, "Z")

    # Check if two smaller dimensions are similar (circular cross-section indicator)
    cross_section_similar = False
    if min_dim > 0:
        ratio = mid_dim / min_dim
        cross_section_similar = ratio <= (1 + tolerance)

    # Calculate elongation ratio
    avg_cross = (min_dim + mid_dim) / 2.0 if (min_dim + mid_dim) > 0 else 1.0
    elongation = max_dim / avg_cross if avg_cross > 0 else 1.0

    # Detect shape type
    is_elongated = elongation >= elongated_ratio and cross_section_similar

    # Disc detection: two large dimensions similar, one small
    large_dims_similar = False
    if mid_dim > 0:
        large_ratio = max_dim / mid_dim
        large_dims_similar = large_ratio <= (1 + tolerance)

    is_disc = large_dims_similar and (min_dim < mid_dim * 0.5) if mid_dim > 0 else False

    # For disc, axis is along the thin dimension
    if is_disc:
        min_axis = axis_map.get(min_dim, "Z")
        cylinder_axis = min_axis
    elif is_elongated:
        cylinder_axis = max_axis
    else:
        cylinder_axis = None

    # Calculate shape score (0-1, higher = more cylindrical)
    shape_score = 0.0
    reasoning_parts = []

    if is_elongated:
        # Score based on cross-section similarity and elongation
        cross_score = 1.0 - abs(1.0 - (mid_dim / min_dim)) if min_dim > 0 else 0.0
        elong_score = min(elongation / 3.0, 1.0)  # Max score at 3:1 elongation
        shape_score = (cross_score * 0.6 + elong_score * 0.4)
        reasoning_parts.append(f"Elongated shape (ratio {elongation:.1f}:1)")
        reasoning_parts.append(f"Cross-section similarity: {cross_score*100:.0f}%")
    elif is_disc:
        # Score based on large dimensions similarity
        disc_score = 1.0 - abs(1.0 - (max_dim / mid_dim)) if mid_dim > 0 else 0.0
        thin_ratio = min_dim / mid_dim if mid_dim > 0 else 1.0
        thinness_score = 1.0 - thin_ratio  # Thinner = more disc-like
        shape_score = (disc_score * 0.5 + thinness_score * 0.5)
        reasoning_parts.append(f"Disc/flange shape (thin axis: {min_dim:.1f}mm)")
    else:
        # Check if it's at least somewhat elongated
        if elongation > 1.2:
            shape_score = 0.2 * (elongation - 1.0)
            reasoning_parts.append(f"Slightly elongated (ratio {elongation:.1f}:1)")
        else:
            reasoning_parts.append("Cubic/prismatic shape - not cylindrical")

    return {
        "is_elongated": is_elongated,
        "is_disc": is_disc,
        "elongation_ratio": round(elongation, 2),
        "cross_section_similar": cross_section_similar,
        "cylinder_axis": cylinder_axis,
        "shape_score": round(min(shape_score, 1.0), 3),
        "sorted_dims_mm": sorted_dims,
        "reasoning": "; ".join(reasoning_parts)
    }


def _calculate_enclosing_diameter(dimensions: Dict[str, float], axis: Optional[str]) -> float:
    """
    Calculate the minimum round stock diameter needed to enclose the part.

    For a given axis, the enclosing diameter is the diagonal of the
    cross-section perpendicular to that axis.

    Args:
        dimensions: Dict with x_mm, y_mm, z_mm
        axis: Cylinder axis ("X", "Y", or "Z"), or None for max diagonal

    Returns:
        Enclosing diameter in mm
    """
    x = dimensions["x_mm"]
    y = dimensions["y_mm"]
    z = dimensions["z_mm"]

    if axis == "X":
        # Cross-section is Y-Z plane
        diameter = math.sqrt(y**2 + z**2)
    elif axis == "Y":
        # Cross-section is X-Z plane
        diameter = math.sqrt(x**2 + z**2)
    elif axis == "Z":
        # Cross-section is X-Y plane
        diameter = math.sqrt(x**2 + y**2)
    else:
        # No specific axis - use maximum diagonal
        diameter = max(
            math.sqrt(y**2 + z**2),
            math.sqrt(x**2 + z**2),
            math.sqrt(x**2 + y**2)
        )

    return round(diameter, 2)


def detect_cylindrical_part(
    body,
    features: Optional[List[Dict[str, Any]]] = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Detect if a part is suitable for round stock (lathe candidate).

    Combines bounding box shape analysis with face geometry counting to
    determine if a part is likely cylindrical. Returns confidence score,
    reasoning, and trade-offs for rectangular vs round stock.

    Args:
        body: BRepBody to analyze
        features: Optional list of detected features from Phase 2
                  (reserved for future enhancement, not used in v1)
        config: Optional configuration dict (uses DEFAULT_CONFIG if None)

    Returns:
        Dict containing:
        - is_cylindrical: bool - True if likely lathe candidate
        - confidence: float - 0.0-1.0 confidence score
        - reasoning: str - Human-readable explanation
        - cylinder_axis: str or None - "X", "Y", or "Z" if cylindrical
        - enclosing_diameter_mm: float - Minimum round stock diameter needed
        - trade_offs: dict or None - Rectangular vs round stock comparison

    Example:
        >>> result = detect_cylindrical_part(body)
        >>> if result["is_cylindrical"]:
        ...     print(f"Round stock diameter: {result['enclosing_diameter_mm']}mm")
        ...     print(result["trade_offs"]["round"])
    """
    cfg = config if config is not None else DEFAULT_CONFIG
    threshold = cfg.get("cylindrical_threshold", 0.5)
    face_weight = cfg.get("face_score_weight", 0.6)
    bbox_weight = cfg.get("bbox_score_weight", 0.4)

    # Get bounding box dimensions
    dimensions = _get_bounding_box_dimensions(body)

    if dimensions is None:
        return {
            "is_cylindrical": False,
            "confidence": 0.0,
            "reasoning": "Unable to analyze bounding box - Fusion API not available or body invalid",
            "cylinder_axis": None,
            "enclosing_diameter_mm": 0.0,
            "trade_offs": None
        }

    # Analyze bounding box shape
    shape_analysis = _analyze_bounding_box_shape(dimensions, cfg)

    # Count cylindrical faces
    cyl_faces, total_faces = _count_cylindrical_faces(body)

    # Calculate face ratio score
    face_ratio = cyl_faces / total_faces if total_faces > 0 else 0.0

    # Build reasoning
    reasoning_parts = [shape_analysis["reasoning"]]

    if total_faces > 0:
        reasoning_parts.append(f"Cylindrical faces: {cyl_faces}/{total_faces} ({face_ratio*100:.0f}%)")

    # Combine scores: face_ratio * 0.6 + bbox_shape * 0.4
    combined_score = (face_ratio * face_weight) + (shape_analysis["shape_score"] * bbox_weight)
    combined_score = round(min(combined_score, 1.0), 3)

    # Determine if cylindrical based on threshold
    is_cylindrical = combined_score >= threshold

    # Get axis and enclosing diameter
    axis = shape_analysis["cylinder_axis"]
    enclosing_diameter = _calculate_enclosing_diameter(dimensions, axis)

    # Build final reasoning
    if is_cylindrical:
        if face_ratio > 0.5:
            reasoning_parts.append("High proportion of cylindrical surfaces")
        if shape_analysis["is_elongated"]:
            reasoning_parts.append("Elongated profile suitable for turning")
        if shape_analysis["is_disc"]:
            reasoning_parts.append("Disc/flange profile suitable for facing")
        reasoning_parts.append(f"Confidence: {combined_score*100:.0f}%")
    else:
        reasoning_parts.append(f"Below cylindrical threshold ({threshold*100:.0f}%)")

    # Trade-offs for cylindrical parts per CONTEXT.md
    trade_offs = None
    if is_cylindrical:
        trade_offs = {
            "rectangular": "More stable fixturing, easier to clamp in vise, better for features requiring XY indexing",
            "round": "Less material waste, faster for cylindrical parts, natural for turning operations"
        }

    return {
        "is_cylindrical": is_cylindrical,
        "confidence": combined_score,
        "reasoning": "; ".join(reasoning_parts),
        "cylinder_axis": axis,
        "enclosing_diameter_mm": enclosing_diameter,
        "trade_offs": trade_offs
    }
