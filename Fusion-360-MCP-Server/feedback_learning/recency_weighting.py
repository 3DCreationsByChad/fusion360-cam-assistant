"""
Recency Weighting for Fusion 360 CAM Assistant.

Provides exponential decay time-based weighting for feedback events.
Recent feedback is weighted more heavily than old feedback using the formula:
W = e^(-lambda * t) where lambda = ln(2) / halflife_days, t = age in days

Per CONTEXT.md:
- Exponential decay with configurable halflife (default 30 days)
- Explicit feedback (good/bad) counts 2x weight compared to implicit accept/reject
- Weighted acceptance rate calculation for confidence adjustment

Functions:
    calculate_recency_weight: Calculate exponential decay weight for a timestamp
    get_weighted_acceptance_rate: Calculate weighted acceptance rate from feedback history
"""

from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone
import math


def calculate_recency_weight(
    feedback_timestamp: str,
    halflife_days: float = 30.0
) -> float:
    """
    Calculate exponential decay weight for a feedback event based on its age.

    Uses formula: W = e^(-lambda * t)
    where lambda = ln(2) / halflife_days, t = age in days

    Args:
        feedback_timestamp: ISO timestamp string from SQLite (e.g., "2026-02-05 14:30:00")
        halflife_days: Number of days for weight to decay to 50% (default: 30.0)

    Returns:
        Weight value between 0.0 and 1.0

    Example:
        >>> weight = calculate_recency_weight("2026-01-01 12:00:00", halflife_days=30.0)
        >>> # Recent events have weight near 1.0, old events near 0.0
    """
    try:
        # Parse timestamp - handle both with and without 'Z' suffix
        timestamp_str = feedback_timestamp.replace('Z', '+00:00')
        if '+' not in timestamp_str and '-' not in timestamp_str[-6:]:
            # No timezone info, assume UTC
            feedback_dt = datetime.fromisoformat(timestamp_str).replace(tzinfo=timezone.utc)
        else:
            feedback_dt = datetime.fromisoformat(timestamp_str)

        # Get current time (UTC-aware)
        now = datetime.now(timezone.utc)

        # Calculate age in days
        age_seconds = (now - feedback_dt).total_seconds()
        age_days = age_seconds / 86400.0  # 86400 seconds per day

        # Calculate exponential decay weight
        # lambda = ln(2) / halflife
        decay_lambda = math.log(2) / halflife_days
        weight = math.exp(-decay_lambda * age_days)

        # Clamp to [0.0, 1.0]
        weight = max(0.0, min(1.0, weight))

        return weight

    except Exception:
        # On error, return neutral weight
        return 0.5


def get_weighted_acceptance_rate(
    feedback_history: List[Dict[str, Any]],
    halflife_days: float = 30.0
) -> Tuple[float, int]:
    """
    Calculate weighted acceptance rate from feedback history.

    Applies exponential decay recency weighting and 2x multiplier for explicit feedback.

    Args:
        feedback_history: List of feedback event dicts, each with:
            - created_at: ISO timestamp string
            - feedback_type: 'implicit_accept', 'implicit_reject', 'explicit_good', 'explicit_bad'
        halflife_days: Number of days for weight to decay to 50% (default: 30.0)

    Returns:
        Tuple of (acceptance_rate, sample_count):
        - acceptance_rate: Weighted acceptance rate (0.0 to 1.0)
        - sample_count: Number of feedback events processed

    Example:
        >>> history = [
        ...     {"created_at": "2026-02-01 10:00:00", "feedback_type": "implicit_accept"},
        ...     {"created_at": "2026-01-15 14:00:00", "feedback_type": "explicit_good"}
        ... ]
        >>> rate, count = get_weighted_acceptance_rate(history)
        >>> print(f"Acceptance rate: {rate:.1%} from {count} samples")
    """
    if not feedback_history:
        return (0.5, 0)  # Neutral default for empty history

    weighted_total = 0.0
    weighted_accepts = 0.0
    sample_count = len(feedback_history)

    for event in feedback_history:
        created_at = event.get("created_at")
        feedback_type = event.get("feedback_type", "")

        if not created_at:
            continue

        # Calculate recency weight
        recency_weight = calculate_recency_weight(created_at, halflife_days)

        # Apply 2x multiplier for explicit feedback (per CONTEXT.md)
        if feedback_type.startswith("explicit_"):
            recency_weight *= 2.0

        # Add to weighted total
        weighted_total += recency_weight

        # If accepted/good, add to weighted accepts
        if feedback_type in ("implicit_accept", "explicit_good"):
            weighted_accepts += recency_weight

    # Calculate acceptance rate
    if weighted_total < 0.01:
        return (0.5, 0)  # Neutral default if negligible weight

    acceptance_rate = weighted_accepts / weighted_total

    # Clamp to [0.0, 1.0] and round
    acceptance_rate = max(0.0, min(1.0, acceptance_rate))

    return (acceptance_rate, sample_count)
