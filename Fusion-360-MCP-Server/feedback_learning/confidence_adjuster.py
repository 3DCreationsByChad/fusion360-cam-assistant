"""
Confidence Adjuster for Fusion 360 CAM Assistant.

Provides confidence score adjustment based on user feedback history.
Blends default rule-based confidence with weighted acceptance rate from
feedback events.

Per CONTEXT.md:
- Requires 3+ samples before adjusting confidence (MIN_SAMPLES)
- Confidence never drops below 0.20 floor (CONFIDENCE_FLOOR)
- Full trust in feedback at 10+ samples (FULL_TRUST_SAMPLES)
- Tentative threshold at 0.60 for flagging low-confidence suggestions

Functions:
    adjust_confidence_from_feedback: Blend base confidence with acceptance rate
    should_notify_learning: Check if just crossed learning threshold
"""

from typing import List, Dict, Any, Tuple
from .recency_weighting import get_weighted_acceptance_rate


# =============================================================================
# CONSTANTS
# =============================================================================

# Minimum samples required before adjusting confidence (CONTEXT.md decision)
MIN_SAMPLES = 3

# Confidence floor - prevents death spiral (Research open question #3)
CONFIDENCE_FLOOR = 0.20

# At this many samples, fully trust acceptance rate over base confidence
FULL_TRUST_SAMPLES = 10

# Flag as tentative below this threshold (CONTEXT.md decision)
TENTATIVE_THRESHOLD = 0.60


# =============================================================================
# CONFIDENCE ADJUSTMENT
# =============================================================================

def adjust_confidence_from_feedback(
    base_confidence: float,
    feedback_history: List[Dict[str, Any]],
    min_samples: int = MIN_SAMPLES,
    halflife_days: float = 30.0
) -> Tuple[float, str]:
    """
    Adjust confidence score based on user feedback history.

    Blends base confidence (from default rules) with weighted acceptance rate
    (from user feedback). Blend ratio increases with sample count.

    Args:
        base_confidence: Default confidence from rules (0.0 to 1.0)
        feedback_history: List of feedback event dicts with created_at and feedback_type
        min_samples: Minimum samples required before adjusting (default: MIN_SAMPLES=3)
        halflife_days: Halflife for recency weighting (default: 30.0)

    Returns:
        Tuple of (adjusted_confidence, source_tag):
        - adjusted_confidence: Blended confidence score (0.0 to 1.0)
        - source_tag: 'default_rules', 'user_preference', or 'user_preference_tentative'

    Example:
        >>> history = [{"created_at": "...", "feedback_type": "implicit_accept"}, ...]
        >>> confidence, source = adjust_confidence_from_feedback(0.75, history)
        >>> print(f"Confidence: {confidence:.2f} ({source})")
    """
    # If insufficient samples, return base confidence unchanged
    if len(feedback_history) < min_samples:
        return (base_confidence, "default_rules")

    # Calculate weighted acceptance rate
    acceptance_rate, sample_count = get_weighted_acceptance_rate(
        feedback_history,
        halflife_days
    )

    # Calculate blend weight based on sample count
    # Linear ramp from 0.0 at min_samples to 1.0 at FULL_TRUST_SAMPLES
    sample_weight = min(1.0, sample_count / FULL_TRUST_SAMPLES)

    # Blend base confidence with acceptance rate
    # adjusted = base * (1 - weight) + acceptance * weight
    adjusted = base_confidence * (1 - sample_weight) + acceptance_rate * sample_weight

    # Apply confidence floor to prevent death spiral
    adjusted = max(CONFIDENCE_FLOOR, adjusted)

    # Determine source tag
    if adjusted < TENTATIVE_THRESHOLD:
        source_tag = "user_preference_tentative"
    else:
        source_tag = "user_preference"

    # Round to 2 decimal places
    adjusted = round(adjusted, 2)

    return (adjusted, source_tag)


def should_notify_learning(feedback_history: List[Dict[str, Any]]) -> bool:
    """
    Check if we just crossed the learning threshold.

    Returns True when feedback_history length exactly equals MIN_SAMPLES,
    indicating this is the first time we have enough data to learn.

    Args:
        feedback_history: List of feedback event dicts

    Returns:
        True if just crossed MIN_SAMPLES threshold, False otherwise

    Example:
        >>> history = [event1, event2, event3]
        >>> if should_notify_learning(history):
        ...     print("Learning now active for this context!")
    """
    return len(feedback_history) == MIN_SAMPLES
