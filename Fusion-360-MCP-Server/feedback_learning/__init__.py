"""
Feedback Learning Module for Fusion 360 CAM Assistant.

This module provides the core data and computation layer for learning from
user feedback on CAM suggestions. It tracks user choices, acceptance/rejection
of suggestions, and explicit good/bad feedback, then uses this history to
improve future recommendations.

Key Features:
- SQLite-based feedback storage with full context snapshots
- Exponential decay recency weighting (recent feedback counts more)
- Confidence adjustment based on weighted acceptance rates
- Material family matching for cross-material learning
- Per-operation-type feedback tracking and statistics

Architecture:
- feedback_store: SQLite schema and CRUD operations
- recency_weighting: Exponential decay time-based weighting
- confidence_adjuster: Blends default confidence with acceptance rates
- context_matcher: Field-based querying and conflict detection

Per CONTEXT.md:
- Minimum 3 samples required before adjusting confidence
- Explicit feedback (good/bad) counts 2x weight vs implicit accept/reject
- Confidence never drops below 0.20 floor
- Per-category reset capability for targeted learning resets

Example:
    >>> from feedback_learning import (
    ...     initialize_feedback_schema,
    ...     record_feedback,
    ...     get_matching_feedback,
    ...     adjust_confidence_from_feedback
    ... )
    >>> from mcp_bridge import call as mcp_call
    >>>
    >>> # Initialize schema
    >>> initialize_feedback_schema(mcp_call)
    >>>
    >>> # Record feedback event
    >>> record_feedback(
    ...     "stock_setup",
    ...     "aluminum",
    ...     "pocket-heavy",
    ...     context={"bounding_box": {...}},
    ...     suggestion={"stock_dimensions": {...}, "confidence_score": 0.85},
    ...     user_choice=None,  # Accepted as-is
    ...     feedback_type="implicit_accept",
    ...     note=None,
    ...     mcp_call_func=mcp_call
    ... )
    >>>
    >>> # Query matching feedback
    >>> history = get_matching_feedback("stock_setup", "aluminum", "pocket-heavy", mcp_call_func=mcp_call)
    >>>
    >>> # Adjust confidence based on feedback
    >>> adjusted, source = adjust_confidence_from_feedback(0.85, history)
    >>> print(f"Confidence: {adjusted:.2f} ({source})")
"""

from .feedback_store import (
    initialize_feedback_schema,
    record_feedback,
    get_feedback_statistics,
    export_feedback_history,
    clear_feedback_history,
    FEEDBACK_HISTORY_SCHEMA
)
from .recency_weighting import (
    calculate_recency_weight,
    get_weighted_acceptance_rate
)
from .confidence_adjuster import (
    adjust_confidence_from_feedback,
    should_notify_learning,
    MIN_SAMPLES,
    CONFIDENCE_FLOOR,
    TENTATIVE_THRESHOLD
)
from .context_matcher import (
    get_matching_feedback,
    get_conflicting_choices
)

__all__ = [
    # Feedback storage
    "initialize_feedback_schema",
    "record_feedback",
    "get_feedback_statistics",
    "export_feedback_history",
    "clear_feedback_history",
    "FEEDBACK_HISTORY_SCHEMA",
    # Recency weighting
    "calculate_recency_weight",
    "get_weighted_acceptance_rate",
    # Confidence adjustment
    "adjust_confidence_from_feedback",
    "should_notify_learning",
    "MIN_SAMPLES",
    "CONFIDENCE_FLOOR",
    "TENTATIVE_THRESHOLD",
    # Context matching
    "get_matching_feedback",
    "get_conflicting_choices",
]
