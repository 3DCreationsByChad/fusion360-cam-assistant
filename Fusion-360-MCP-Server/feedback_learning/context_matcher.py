"""
Context Matcher for Fusion 360 CAM Assistant.

Provides field-based querying of feedback history and conflict detection.
Matches feedback events by operation_type, material family, and geometry_type.

Per CONTEXT.md:
- Material family matching using LIKE (partial matching)
- Lowercase normalization for consistent keying
- Conflict detection for showing multiple choice alternatives

Functions:
    get_matching_feedback: Query feedback by operation_type + material + geometry_type
    get_conflicting_choices: Detect conflicting user choices in feedback history
"""

from typing import List, Dict, Any, Optional, Callable
import json


# MCP bridge SQLite tool unlock token (from mcp_bridge.py docs)
SQLITE_TOOL_UNLOCK_TOKEN = "29e63eb5"


# =============================================================================
# FEEDBACK MATCHING
# =============================================================================

def get_matching_feedback(
    operation_type: str,
    material: str,
    geometry_type: str,
    limit: int = 50,
    mcp_call_func: Callable = None
) -> List[Dict[str, Any]]:
    """
    Query feedback history matching operation_type, material family, and geometry_type.

    Uses LIKE for material matching to support partial matches (e.g., "6061 aluminum"
    matches "aluminum" family).

    Args:
        operation_type: Operation type to match exactly
        material: Material name (will be normalized to lowercase, matched with LIKE)
        geometry_type: Geometry type to match exactly (normalized to lowercase)
        limit: Maximum number of rows to return (default: 50)
        mcp_call_func: MCP call function for SQLite operations

    Returns:
        List of feedback event dicts with parsed JSON fields, ordered by created_at DESC.
        Returns empty list on error.

    Example:
        >>> matching = get_matching_feedback(
        ...     "stock_setup",
        ...     "aluminum",
        ...     "pocket-heavy",
        ...     limit=20,
        ...     mcp_call_func=mcp_call
        ... )
        >>> print(f"Found {len(matching)} matching events")
    """
    # Normalize material and geometry_type to lowercase
    material_key = material.lower().strip()
    geometry_key = geometry_type.lower().strip()

    try:
        # Query matching feedback with LIKE for material family matching
        result = mcp_call_func("sqlite", {
            "input": {
                "sql": """
                    SELECT id, operation_type, material, geometry_type,
                           context_snapshot, suggestion_payload, user_choice,
                           feedback_type, feedback_note, confidence_before, created_at
                    FROM cam_feedback_history
                    WHERE operation_type = ?
                      AND material LIKE ?
                      AND geometry_type = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                "params": [
                    operation_type,
                    f"%{material_key}%",  # LIKE pattern for family matching
                    geometry_key,
                    limit
                ],
                "tool_unlock_token": SQLITE_TOOL_UNLOCK_TOKEN
            }
        })

        feedback_events = []
        if result and isinstance(result, dict):
            rows = result.get("rows") or result.get("data") or result.get("result")
            if rows:
                for row in rows:
                    # Handle both dict and list row formats
                    if isinstance(row, dict):
                        event = {
                            "id": row.get("id"),
                            "operation_type": row.get("operation_type"),
                            "material": row.get("material"),
                            "geometry_type": row.get("geometry_type"),
                            "feedback_type": row.get("feedback_type"),
                            "feedback_note": row.get("feedback_note"),
                            "confidence_before": row.get("confidence_before"),
                            "created_at": row.get("created_at")
                        }
                        # Parse JSON fields
                        try:
                            event["context_snapshot"] = json.loads(row.get("context_snapshot", "{}"))
                        except:
                            event["context_snapshot"] = {}
                        try:
                            event["suggestion_payload"] = json.loads(row.get("suggestion_payload", "{}"))
                        except:
                            event["suggestion_payload"] = {}
                        try:
                            user_choice_str = row.get("user_choice")
                            event["user_choice"] = json.loads(user_choice_str) if user_choice_str else None
                        except:
                            event["user_choice"] = None

                        feedback_events.append(event)

                    elif isinstance(row, (list, tuple)) and len(row) >= 11:
                        event = {
                            "id": row[0],
                            "operation_type": row[1],
                            "material": row[2],
                            "geometry_type": row[3],
                            "feedback_type": row[7],
                            "feedback_note": row[8],
                            "confidence_before": row[9],
                            "created_at": row[10]
                        }
                        # Parse JSON fields
                        try:
                            event["context_snapshot"] = json.loads(row[4]) if row[4] else {}
                        except:
                            event["context_snapshot"] = {}
                        try:
                            event["suggestion_payload"] = json.loads(row[5]) if row[5] else {}
                        except:
                            event["suggestion_payload"] = {}
                        try:
                            event["user_choice"] = json.loads(row[6]) if row[6] else None
                        except:
                            event["user_choice"] = None

                        feedback_events.append(event)

        return feedback_events

    except Exception:
        # Never raise - return empty list on error
        return []


# =============================================================================
# CONFLICT DETECTION
# =============================================================================

def get_conflicting_choices(feedback_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detect conflicting user choices in feedback history.

    Groups feedback by user_choice (serialized as JSON for comparison).
    If multiple distinct choices exist, returns them as alternatives.

    Args:
        feedback_history: List of feedback event dicts with user_choice key

    Returns:
        List of alternative choice dicts, each with:
        - choice: The user choice dict
        - count: Number of times this choice was made
        - most_recent_date: ISO timestamp of most recent occurrence
        - weighted_score: Recency-weighted score for ranking

        Returns empty list if no conflicts (only one distinct choice or all None).

    Example:
        >>> conflicts = get_conflicting_choices(feedback_history)
        >>> if conflicts:
        ...     print(f"Found {len(conflicts)} conflicting choices")
        ...     for alt in conflicts:
        ...         print(f"  Choice: {alt['choice']} (used {alt['count']} times)")
    """
    if not feedback_history:
        return []

    # Group by user_choice (serialize for comparison)
    choice_groups = {}

    for event in feedback_history:
        user_choice = event.get("user_choice")
        created_at = event.get("created_at", "")

        # Serialize choice for grouping (None becomes "null")
        choice_key = json.dumps(user_choice, sort_keys=True)

        if choice_key not in choice_groups:
            choice_groups[choice_key] = {
                "choice": user_choice,
                "count": 0,
                "most_recent_date": created_at,
                "events": []
            }

        choice_groups[choice_key]["count"] += 1
        choice_groups[choice_key]["events"].append(event)

        # Update most recent date
        if created_at > choice_groups[choice_key]["most_recent_date"]:
            choice_groups[choice_key]["most_recent_date"] = created_at

    # If only one distinct choice (or all None), no conflict
    if len(choice_groups) <= 1:
        return []

    # Calculate weighted scores for ranking
    # For now, simple score = count (could enhance with recency weighting)
    alternatives = []
    for choice_key, group in choice_groups.items():
        alternatives.append({
            "choice": group["choice"],
            "count": group["count"],
            "most_recent_date": group["most_recent_date"],
            "weighted_score": group["count"]  # Simple count-based score
        })

    # Sort by weighted_score descending (most popular first)
    alternatives.sort(key=lambda x: x["weighted_score"], reverse=True)

    return alternatives
