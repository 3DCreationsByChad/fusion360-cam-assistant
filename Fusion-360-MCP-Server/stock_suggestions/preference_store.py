"""
Preference Store for Fusion 360 CAM Assistant.

Provides SQLite-based storage and retrieval for CAM stock preferences,
keyed by material + geometry_type. Uses MCP bridge for SQLite operations.

Per CONTEXT.md:
- Preferences keyed by material + geometry type (e.g., "aluminum + pocket-heavy")
- Always show source attribution ('from: user_preference' or 'from: default')
- Full preference profile includes: offsets, preferred_orientation, stock_shape, machining_allowance
"""

from typing import Dict, Any, Optional, List, Callable


# =============================================================================
# SCHEMA DEFINITIONS
# =============================================================================

STOCK_PREFERENCES_SCHEMA = """
CREATE TABLE IF NOT EXISTS cam_stock_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material TEXT NOT NULL,
    geometry_type TEXT NOT NULL,
    offsets_xy_mm REAL DEFAULT 5.0,
    offsets_z_mm REAL DEFAULT 2.5,
    preferred_orientation TEXT,
    stock_shape TEXT DEFAULT 'rectangular',
    machining_allowance_mm REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(material, geometry_type)
);
"""

MACHINE_PROFILES_SCHEMA = """
CREATE TABLE IF NOT EXISTS cam_machine_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    machine_type TEXT NOT NULL,
    max_x_mm REAL,
    max_y_mm REAL,
    max_z_mm REAL,
    spindle_max_rpm INTEGER,
    has_4th_axis INTEGER DEFAULT 0,
    has_5th_axis INTEGER DEFAULT 0,
    post_processor TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# MCP bridge SQLite tool unlock token (from sqlite MCP server docs)
SQLITE_TOOL_UNLOCK_TOKEN = "8d8f7853"

# Persistent database file for CAM preferences
CAM_PREFERENCES_DATABASE = "@user_data/cam_preferences.db"


# =============================================================================
# SCHEMA INITIALIZATION
# =============================================================================

def initialize_schema(mcp_call_func: Callable) -> bool:
    """
    Initialize the SQLite schema for CAM preferences and machine profiles.

    Creates tables if they don't exist. Safe to call multiple times.

    Args:
        mcp_call_func: MCP call function (e.g., mcp.call)
                       Should accept (tool_name, arguments) and return result dict

    Returns:
        True on success, False on error

    Example:
        >>> from mcp_bridge import call as mcp_call
        >>> success = initialize_schema(mcp_call)
    """
    try:
        # Create stock preferences table
        result1 = mcp_call_func("sqlite", {
            "input": {
                "database": CAM_PREFERENCES_DATABASE,
                "sql": STOCK_PREFERENCES_SCHEMA,
                "params": [],
                "tool_unlock_token": SQLITE_TOOL_UNLOCK_TOKEN
            }
        })

        # Create machine profiles table
        result2 = mcp_call_func("sqlite", {
            "input": {
                "database": CAM_PREFERENCES_DATABASE,
                "sql": MACHINE_PROFILES_SCHEMA,
                "params": [],
                "tool_unlock_token": SQLITE_TOOL_UNLOCK_TOKEN
            }
        })

        # Check for errors in results
        if result1 and isinstance(result1, dict) and result1.get("error"):
            return False
        if result2 and isinstance(result2, dict) and result2.get("error"):
            return False

        return True

    except Exception:
        return False


# =============================================================================
# PREFERENCE OPERATIONS
# =============================================================================

def get_preference(
    material: str,
    geometry_type: str,
    mcp_call_func: Callable
) -> Optional[Dict[str, Any]]:
    """
    Retrieve a stored preference by material and geometry type.

    Args:
        material: Material name (e.g., "aluminum", "steel")
        geometry_type: Geometry classification (e.g., "pocket-heavy", "hole-heavy")
        mcp_call_func: MCP call function for SQLite operations

    Returns:
        Dict containing preference data with source attribution, or None if not found:
        - offsets_xy_mm: float
        - offsets_z_mm: float
        - preferred_orientation: str or None
        - stock_shape: str
        - machining_allowance_mm: float or None
        - source: "from: user_preference"

    Example:
        >>> pref = get_preference("aluminum", "pocket-heavy", mcp_call)
        >>> if pref:
        ...     print(f"XY offset: {pref['offsets_xy_mm']}mm ({pref['source']})")
    """
    # Normalize inputs to lowercase for consistent keying
    material_key = material.lower().strip()
    geometry_key = geometry_type.lower().strip()

    try:
        result = mcp_call_func("sqlite", {
            "input": {
                "database": CAM_PREFERENCES_DATABASE,
                "sql": """
                    SELECT offsets_xy_mm, offsets_z_mm, preferred_orientation,
                           stock_shape, machining_allowance_mm
                    FROM cam_stock_preferences
                    WHERE material = ? AND geometry_type = ?
                """,
                "params": [material_key, geometry_key],
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
                        "offsets_xy_mm": row.get("offsets_xy_mm", 5.0),
                        "offsets_z_mm": row.get("offsets_z_mm", 2.5),
                        "preferred_orientation": row.get("preferred_orientation"),
                        "stock_shape": row.get("stock_shape", "rectangular"),
                        "machining_allowance_mm": row.get("machining_allowance_mm"),
                        "source": "from: user_preference"
                    }
                elif isinstance(row, (list, tuple)) and len(row) >= 5:
                    return {
                        "offsets_xy_mm": row[0] if row[0] is not None else 5.0,
                        "offsets_z_mm": row[1] if row[1] is not None else 2.5,
                        "preferred_orientation": row[2],
                        "stock_shape": row[3] if row[3] is not None else "rectangular",
                        "machining_allowance_mm": row[4],
                        "source": "from: user_preference"
                    }

        return None

    except Exception:
        return None


def save_preference(
    material: str,
    geometry_type: str,
    preference_dict: Dict[str, Any],
    mcp_call_func: Callable
) -> bool:
    """
    Store or update a preference by material and geometry type.

    Uses INSERT OR REPLACE to upsert the preference record.

    Args:
        material: Material name (e.g., "aluminum", "steel")
        geometry_type: Geometry classification (e.g., "pocket-heavy", "hole-heavy")
        preference_dict: Dict containing preference values:
            - offsets_xy_mm: float (default: 5.0)
            - offsets_z_mm: float (default: 2.5)
            - preferred_orientation: str or None
            - stock_shape: str (default: "rectangular")
            - machining_allowance_mm: float or None
        mcp_call_func: MCP call function for SQLite operations

    Returns:
        True on success, False on error

    Example:
        >>> save_preference("aluminum", "pocket-heavy", {
        ...     "offsets_xy_mm": 6.0,
        ...     "offsets_z_mm": 3.0,
        ...     "stock_shape": "rectangular"
        ... }, mcp_call)
    """
    # Normalize inputs to lowercase for consistent keying
    material_key = material.lower().strip()
    geometry_key = geometry_type.lower().strip()

    # Extract preference values with defaults
    offsets_xy = preference_dict.get("offsets_xy_mm", 5.0)
    offsets_z = preference_dict.get("offsets_z_mm", 2.5)
    preferred_orientation = preference_dict.get("preferred_orientation")
    stock_shape = preference_dict.get("stock_shape", "rectangular")
    machining_allowance = preference_dict.get("machining_allowance_mm")

    try:
        result = mcp_call_func("sqlite", {
            "input": {
                "database": CAM_PREFERENCES_DATABASE,
                "sql": """
                    INSERT OR REPLACE INTO cam_stock_preferences
                    (material, geometry_type, offsets_xy_mm, offsets_z_mm,
                     preferred_orientation, stock_shape, machining_allowance_mm,
                     updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                "params": [
                    material_key,
                    geometry_key,
                    offsets_xy,
                    offsets_z,
                    preferred_orientation,
                    stock_shape,
                    machining_allowance
                ],
                "tool_unlock_token": SQLITE_TOOL_UNLOCK_TOKEN
            }
        })

        # DEBUG: Log what we actually got back
        import json
        print(f"[PREFERENCE_STORE DEBUG] save_preference result: {json.dumps(result, indent=2)}")

        # Check for errors
        if result and isinstance(result, dict) and result.get("error"):
            print(f"[PREFERENCE_STORE DEBUG] Error detected: {result.get('error')}")
            return False

        print("[PREFERENCE_STORE DEBUG] All checks passed - returning True")
        return True

    except Exception:
        return False


# =============================================================================
# GEOMETRY CLASSIFICATION
# =============================================================================

def classify_geometry_type(features: Optional[List[Dict[str, Any]]]) -> str:
    """
    Classify geometry type based on detected features.

    Categorizes parts by their dominant feature type for preference keying.

    Args:
        features: List of feature dicts from analyze_geometry_for_cam.
                  Each feature should have a "type" key (hole, pocket, slot, etc.)
                  Can be None or empty list.

    Returns:
        Geometry type classification:
        - "simple": Less than 3 features
        - "hole-heavy": >70% holes
        - "pocket-heavy": >70% pockets/slots
        - "mixed": No dominant feature type

    Example:
        >>> features = [{"type": "hole"}, {"type": "hole"}, {"type": "pocket"}]
        >>> classify_geometry_type(features)
        'hole-heavy'
    """
    # Handle empty or None features
    if not features or len(features) < 3:
        return "simple"

    # Count feature types
    hole_count = 0
    pocket_slot_count = 0
    total_count = 0

    for feature in features:
        feature_type = feature.get("type", "").lower()

        # Skip error entries
        if "error" in feature_type:
            continue

        total_count += 1

        if feature_type == "hole":
            hole_count += 1
        elif feature_type in ("pocket", "slot"):
            pocket_slot_count += 1

    # Calculate percentages
    if total_count == 0:
        return "simple"

    hole_pct = hole_count / total_count
    pocket_pct = pocket_slot_count / total_count

    # Classify based on 70% threshold
    if hole_pct > 0.70:
        return "hole-heavy"
    elif pocket_pct > 0.70:
        return "pocket-heavy"
    else:
        return "mixed"
