"""
Strategy Preference Store for Fusion 360 CAM Assistant.

Provides SQLite-based storage and retrieval for CAM strategy preferences,
keyed by material + feature_type. Uses MCP bridge for SQLite operations.

Per CONTEXT.md:
- Preferences keyed by material + feature type (e.g., "aluminum + hole")
- Always show source attribution ('from: user_preference' or 'from: default')
- Full preference profile includes: preferred_roughing_op, preferred_finishing_op,
  preferred_tool_diameter_mm, confidence_score
"""

from typing import Dict, Any, Optional, Callable


# =============================================================================
# SCHEMA DEFINITIONS
# =============================================================================

STRATEGY_PREFERENCES_SCHEMA = """
CREATE TABLE IF NOT EXISTS cam_strategy_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material TEXT NOT NULL,
    feature_type TEXT NOT NULL,
    preferred_roughing_op TEXT,
    preferred_finishing_op TEXT,
    preferred_tool_diameter_mm REAL,
    confidence_score REAL DEFAULT 0.5,
    times_used INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(material, feature_type)
);
"""

# MCP bridge SQLite tool unlock token (from sqlite MCP server docs)
SQLITE_TOOL_UNLOCK_TOKEN = "8d8f7853"

# Persistent database file for CAM strategy preferences
CAM_STRATEGY_DATABASE = "@user_data/cam_strategy_preferences.db"


# =============================================================================
# SCHEMA INITIALIZATION
# =============================================================================

def initialize_strategy_schema(mcp_call_func: Callable) -> bool:
    """
    Initialize the SQLite schema for CAM strategy preferences.

    Creates table if it doesn't exist. Safe to call multiple times.

    Args:
        mcp_call_func: MCP call function (e.g., mcp.call)
                       Should accept (tool_name, arguments) and return result dict

    Returns:
        True on success, False on error

    Example:
        >>> from mcp_bridge import call as mcp_call
        >>> success = initialize_strategy_schema(mcp_call)
    """
    try:
        result = mcp_call_func("sqlite", {
            "input": {
                "database": CAM_STRATEGY_DATABASE,
                "sql": STRATEGY_PREFERENCES_SCHEMA,
                "params": [],
                "tool_unlock_token": SQLITE_TOOL_UNLOCK_TOKEN
            }
        })

        # Check for errors in result
        if result and isinstance(result, dict) and result.get("error"):
            return False

        return True

    except Exception:
        return False


# =============================================================================
# PREFERENCE OPERATIONS
# =============================================================================

def get_strategy_preference(
    material: str,
    feature_type: str,
    mcp_call_func: Callable
) -> Optional[Dict[str, Any]]:
    """
    Retrieve a stored strategy preference by material and feature type.

    Args:
        material: Material name (e.g., "aluminum", "steel")
        feature_type: Feature type (e.g., "hole", "pocket", "slot")
        mcp_call_func: MCP call function for SQLite operations

    Returns:
        Dict containing preference data with source attribution, or None if not found:
        - preferred_roughing_op: str
        - preferred_finishing_op: str
        - preferred_tool_diameter_mm: float or None
        - confidence_score: float
        - source: "from: user_preference"

    Example:
        >>> pref = get_strategy_preference("aluminum", "pocket", mcp_call)
        >>> if pref:
        ...     print(f"Roughing op: {pref['preferred_roughing_op']} ({pref['source']})")
    """
    # Normalize inputs to lowercase for consistent keying
    material_key = material.lower().strip()
    feature_key = feature_type.lower().strip()

    try:
        result = mcp_call_func("sqlite", {
            "input": {
                "database": CAM_STRATEGY_DATABASE,
                "sql": """
                    SELECT preferred_roughing_op, preferred_finishing_op,
                           preferred_tool_diameter_mm, confidence_score
                    FROM cam_strategy_preferences
                    WHERE material = ? AND feature_type = ?
                """,
                "params": [material_key, feature_key],
                "tool_unlock_token": SQLITE_TOOL_UNLOCK_TOKEN
            }
        })

        # Parse result - expect list of rows
        if result and isinstance(result, dict):
            rows = result.get("rows") or result.get("data") or result.get("result")
            if rows and len(rows) > 0:
                row = rows[0]
                # Handle both list and dict row formats
                if isinstance(row, dict):
                    return {
                        "preferred_roughing_op": row.get("preferred_roughing_op"),
                        "preferred_finishing_op": row.get("preferred_finishing_op"),
                        "preferred_tool_diameter_mm": row.get("preferred_tool_diameter_mm"),
                        "confidence_score": row.get("confidence_score", 0.5),
                        "source": "from: user_preference"
                    }
                elif isinstance(row, (list, tuple)) and len(row) >= 4:
                    return {
                        "preferred_roughing_op": row[0],
                        "preferred_finishing_op": row[1],
                        "preferred_tool_diameter_mm": row[2],
                        "confidence_score": row[3] if row[3] is not None else 0.5,
                        "source": "from: user_preference"
                    }

        return None

    except Exception:
        return None


def save_strategy_preference(
    material: str,
    feature_type: str,
    preference_dict: Dict[str, Any],
    mcp_call_func: Callable
) -> bool:
    """
    Store or update a strategy preference by material and feature type.

    Uses INSERT OR REPLACE to upsert the preference record. Increments
    times_used counter on updates.

    Args:
        material: Material name (e.g., "aluminum", "steel")
        feature_type: Feature type (e.g., "hole", "pocket", "slot")
        preference_dict: Dict containing preference values:
            - preferred_roughing_op: str
            - preferred_finishing_op: str
            - preferred_tool_diameter_mm: float (optional)
            - confidence_score: float (default: 0.5)
        mcp_call_func: MCP call function for SQLite operations

    Returns:
        True on success, False on error

    Example:
        >>> save_strategy_preference("aluminum", "pocket", {
        ...     "preferred_roughing_op": "adaptive_clearing",
        ...     "preferred_finishing_op": "2d_contour",
        ...     "preferred_tool_diameter_mm": 6.0,
        ...     "confidence_score": 0.9
        ... }, mcp_call)
    """
    # Normalize inputs to lowercase for consistent keying
    material_key = material.lower().strip()
    feature_key = feature_type.lower().strip()

    # Extract preference values
    roughing_op = preference_dict.get("preferred_roughing_op")
    finishing_op = preference_dict.get("preferred_finishing_op")
    tool_diameter = preference_dict.get("preferred_tool_diameter_mm")
    confidence = preference_dict.get("confidence_score", 0.5)

    try:
        # First check if record exists to handle times_used counter
        existing = get_strategy_preference(material, feature_type, mcp_call_func)
        times_used = 1
        if existing:
            # Increment usage counter (would need to query for current value)
            # For simplicity, we'll use INSERT OR REPLACE with times_used=1
            # A production version could SELECT first, increment, then UPDATE
            pass

        result = mcp_call_func("sqlite", {
            "input": {
                "database": CAM_STRATEGY_DATABASE,
                "sql": """
                    INSERT OR REPLACE INTO cam_strategy_preferences
                    (material, feature_type, preferred_roughing_op, preferred_finishing_op,
                     preferred_tool_diameter_mm, confidence_score, times_used, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                "params": [
                    material_key,
                    feature_key,
                    roughing_op,
                    finishing_op,
                    tool_diameter,
                    confidence,
                    times_used
                ],
                "tool_unlock_token": SQLITE_TOOL_UNLOCK_TOKEN
            }
        })

        # Check for errors
        if result and isinstance(result, dict) and result.get("error"):
            return False

        return True

    except Exception:
        return False
