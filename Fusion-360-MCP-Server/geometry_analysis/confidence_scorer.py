"""
Confidence Scoring Module for Fusion 360 CAM Assistant.

Provides confidence scoring heuristics for feature detection results.
Each detected feature receives a confidence score (0.0-1.0) and reasoning
text explaining the classification.

Exports:
    CONFIDENCE_THRESHOLDS: Threshold values for confidence levels
    calculate_confidence: Calculate confidence score from detection source
    needs_review: Check if confidence requires human review
    get_ambiguity_flags: Identify ambiguous conditions in features
"""

from typing import List, Dict, Any, Tuple


# =============================================================================
# CONSTANTS
# =============================================================================

CONFIDENCE_THRESHOLDS = {
    "needs_review": 0.80,  # Below this, flag needs_review: true
    "high": 0.90,
    "medium": 0.70,
    "low": 0.50
}

# Base confidence by detection source (per RESEARCH.md Pattern 4)
BASE_CONFIDENCE = {
    "fusion_api": 0.95,      # RecognizedHole/RecognizedPocket
    "brep_analysis": 0.75,   # Custom BRep loop traversal
    "heuristic": 0.60        # Aspect ratio, depth/diameter rules
}


# =============================================================================
# CONFIDENCE FUNCTIONS
# =============================================================================

def calculate_confidence(
    detection_source: str,
    geometry_complexity: int,
    ambiguity_flags: List[str]
) -> Tuple[float, str]:
    """
    Calculate confidence score and reasoning for a detected feature.

    Args:
        detection_source: "fusion_api", "brep_analysis", or "heuristic"
        geometry_complexity: int 0-10 (0=simple hole, 10=complex multi-segment)
        geometry_complexity should be clamped to 0-10 range
        ambiguity_flags: list of strings describing ambiguous conditions

    Returns:
        Tuple of (confidence_score, reasoning_text)
        - confidence_score: float between 0.30 and 1.0
        - reasoning_text: human-readable explanation of classification

    Example outputs:
        (0.95, "Fusion API detection (simple geometry)")
        (0.75, "Heuristic classification: aspect ratio 3.2:1 suggests slot; ambiguous range (2.5-3.5)")
    """
    # Get base confidence from detection source
    base = BASE_CONFIDENCE.get(detection_source, 0.60)

    # Calculate complexity penalty: max 0.15 reduction
    complexity = max(0, min(10, geometry_complexity))  # Clamp to 0-10
    complexity_penalty = min(complexity / 100, 0.15)

    # Calculate ambiguity penalty: 0.05 per flag, max 0.25 reduction
    ambiguity_penalty = min(len(ambiguity_flags) * 0.05, 0.25)

    # Calculate final confidence with floor at 0.30
    confidence = max(0.30, base - complexity_penalty - ambiguity_penalty)
    confidence = round(confidence, 2)

    # Build reasoning text
    source_names = {
        "fusion_api": "Fusion API",
        "brep_analysis": "BRep analysis",
        "heuristic": "Heuristic classification"
    }
    source_name = source_names.get(detection_source, detection_source)

    # Start with source description
    if complexity <= 2:
        complexity_desc = "simple geometry"
    elif complexity <= 5:
        complexity_desc = "moderate complexity"
    else:
        complexity_desc = "complex geometry"

    reasoning_parts = [f"{source_name} detection ({complexity_desc})"]

    # Add ambiguity notes
    if ambiguity_flags:
        ambiguity_desc = "; ".join(ambiguity_flags)
        reasoning_parts.append(f"Ambiguous: {ambiguity_desc}")

    # Add penalty notes if significant
    if complexity_penalty > 0.05:
        reasoning_parts.append(f"complexity penalty: -{complexity_penalty:.2f}")
    if ambiguity_penalty > 0:
        reasoning_parts.append(f"ambiguity penalty: -{ambiguity_penalty:.2f}")

    reasoning = "; ".join(reasoning_parts)

    return (confidence, reasoning)


def needs_review(confidence: float) -> bool:
    """
    Determine if a feature needs human review based on confidence score.

    Args:
        confidence: Confidence score (0.0-1.0)

    Returns:
        True if confidence is below CONFIDENCE_THRESHOLDS["needs_review"] (0.80)
    """
    return confidence < CONFIDENCE_THRESHOLDS["needs_review"]


def get_ambiguity_flags(feature_type: str, metrics: Dict[str, Any]) -> List[str]:
    """
    Identify ambiguous conditions in a feature based on type and metrics.

    Args:
        feature_type: "pocket", "slot", "hole", or other feature type
        metrics: Dict containing feature measurements:
            - For pockets/slots: "aspect_ratio" (float)
            - For holes: "segment_count" (int)
            - For blind features: "depth" and "diameter" (floats in mm)

    Returns:
        List of strings describing ambiguous conditions found

    Examples:
        get_ambiguity_flags("pocket", {"aspect_ratio": 3.0})
        -> ["aspect_ratio in ambiguous range (2.5-3.5)"]

        get_ambiguity_flags("hole", {"segment_count": 5})
        -> ["complex hole (>3 segments)"]
    """
    flags = []

    # For pockets/slots: Check aspect_ratio in ambiguous range (2.5-3.5)
    if feature_type in ["pocket", "slot"]:
        aspect_ratio = metrics.get("aspect_ratio")
        if aspect_ratio is not None:
            if 2.5 <= aspect_ratio <= 3.5:
                flags.append(f"aspect_ratio in ambiguous range (2.5-3.5): {aspect_ratio:.2f}")

    # For holes: Check segment_count > 3
    if feature_type == "hole":
        segment_count = metrics.get("segment_count", 0)
        if segment_count > 3:
            flags.append(f"complex hole ({segment_count} segments, >3)")

    # For blind features: Check depth/diameter ratio in 3-4:1 range
    depth = metrics.get("depth")
    diameter = metrics.get("diameter")
    if depth is not None and diameter is not None and diameter > 0:
        depth_diameter_ratio = depth / diameter
        if 3.0 <= depth_diameter_ratio <= 4.0:
            flags.append(f"depth/diameter ratio in ambiguous range (3-4:1): {depth_diameter_ratio:.2f}")

    return flags
