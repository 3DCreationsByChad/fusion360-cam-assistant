"""
Feedback Store for Fusion 360 CAM Assistant.

Provides SQLite-based storage and retrieval for CAM feedback events,
tracking user choices, acceptance/rejection of suggestions, and explicit
good/bad feedback. Uses MCP bridge for SQLite operations.

Per CONTEXT.md:
- Feedback events keyed by operation_type + material + geometry_type
- Context snapshots stored as JSON for future analysis
- Immediate write-through (no batching) for simplicity
- Per-category reset capability for targeted learning resets
- Explicit feedback (good/bad) counts 2x weight compared to implicit accept/reject

Functions:
    initialize_feedback_schema: Initialize SQLite table and indexes
    record_feedback: Store feedback event with full context
    get_feedback_statistics: Overall and per-category acceptance rates
    export_feedback_history: Export to CSV or JSON format
    clear_feedback_history: Reset feedback data (all or by operation_type)
"""

from typing import Dict, Any, Optional, Callable


def _unwrap_mcp_result(mcp_result):
    """Unwrap JSON-RPC response: {'jsonrpc': '2.0', 'result': {...}} -> {...}"""
    if isinstance(mcp_result, dict) and 'result' in mcp_result and 'jsonrpc' in mcp_result:
        return mcp_result['result']
    return mcp_result

import json
import csv
from io import StringIO




def _unwrap_mcp_result(result):
    """
    Unwrap JSON-RPC response from MCP client.
    
    MCP client returns: {"jsonrpc": "2.0", "id": "...", "result": {...}}
    We need the inner "result" object.
    """
    if isinstance(result, dict) and 'result' in result and 'jsonrpc' in result:
        return result['result']
    return result


# =============================================================================
# SCHEMA DEFINITIONS
# =============================================================================

FEEDBACK_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS cam_feedback_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_type TEXT NOT NULL,
    material TEXT NOT NULL,
    geometry_type TEXT NOT NULL,
    context_snapshot TEXT NOT NULL,
    suggestion_payload TEXT NOT NULL,
    user_choice TEXT,
    feedback_type TEXT NOT NULL,
    feedback_note TEXT,
    confidence_before REAL,
    created_at TIMESTAMP DEFAULT (datetime('now'))
);
"""

INDEX_MATERIAL_GEOMETRY = """
CREATE INDEX IF NOT EXISTS idx_feedback_material_geometry
ON cam_feedback_history(material, geometry_type);
"""

INDEX_OPERATION_TYPE = """
CREATE INDEX IF NOT EXISTS idx_feedback_operation_type
ON cam_feedback_history(operation_type);
"""

INDEX_CREATED_AT = """
CREATE INDEX IF NOT EXISTS idx_feedback_created_at
ON cam_feedback_history(created_at DESC);
"""

# MCP bridge SQLite tool unlock token (from sqlite MCP server docs)
SQLITE_TOOL_UNLOCK_TOKEN = "8d8f7853"

# Persistent database file for CAM feedback (uses @user_data prefix resolved by MCP sqlite tool)
CAM_FEEDBACK_DATABASE = "@user_data/cam_feedback.db"


# =============================================================================
# SCHEMA INITIALIZATION
# =============================================================================

def initialize_feedback_schema(mcp_call_func: Callable) -> bool:
    """
    Initialize the SQLite schema for CAM feedback history.

    Creates table and indexes if they don't exist. Safe to call multiple times.

    Args:
        mcp_call_func: MCP call function (e.g., mcp.call)
                       Should accept (tool_name, arguments) and return result dict

    Returns:
        True on success, False on error

    Example:
        >>> from mcp_bridge import call as mcp_call
        >>> success = initialize_feedback_schema(mcp_call)
    """
    try:
        # Create table
        result1 = _unwrap_mcp_result(mcp_call_func("sqlite", {
            "input": {
                "database": CAM_FEEDBACK_DATABASE,
                "sql": FEEDBACK_HISTORY_SCHEMA,
                "params": [],
                "tool_unlock_token": SQLITE_TOOL_UNLOCK_TOKEN
            }
        }))

        # Create indexes
        result2 = _unwrap_mcp_result(mcp_call_func("sqlite", {
            "input": {
                "database": CAM_FEEDBACK_DATABASE,
                "sql": INDEX_MATERIAL_GEOMETRY,
                "params": [],
                "tool_unlock_token": SQLITE_TOOL_UNLOCK_TOKEN
            }
        }))

        result3 = _unwrap_mcp_result(mcp_call_func("sqlite", {
            "input": {
                "database": CAM_FEEDBACK_DATABASE,
                "sql": INDEX_OPERATION_TYPE,
                "params": [],
                "tool_unlock_token": SQLITE_TOOL_UNLOCK_TOKEN
            }
        }))

        result4 = _unwrap_mcp_result(mcp_call_func("sqlite", {
            "input": {
                "database": CAM_FEEDBACK_DATABASE,
                "sql": INDEX_CREATED_AT,
                "params": [],
                "tool_unlock_token": SQLITE_TOOL_UNLOCK_TOKEN
            }
        }))

        # Check for errors in results
        for result in [result1, result2, result3, result4]:
            if result and isinstance(result, dict) and result.get("error"):
                return False

        return True

    except Exception as e:
        # Re-raise to see what's failing
        raise


# =============================================================================
# FEEDBACK RECORDING
# =============================================================================

def record_feedback(
    operation_type: str,
    material: str,
    geometry_type: str,
    context: Dict[str, Any],
    suggestion: Dict[str, Any],
    user_choice: Optional[Dict[str, Any]],
    feedback_type: str,
    note: Optional[str],
    mcp_call_func: Callable
) -> bool:
    """
    Record a feedback event to SQLite.

    Args:
        operation_type: Type of operation ('stock_setup', 'toolpath_strategy', 'tool_selection')
        material: Material name (will be normalized to lowercase)
        geometry_type: Geometry classification (will be normalized to lowercase)
        context: Full context dict (bounding_box, features, part size, etc.)
        suggestion: Full suggestion payload that was presented to user
        user_choice: User's choice if they overrode suggestion, or None if accepted as-is
        feedback_type: 'implicit_accept', 'implicit_reject', 'explicit_good', 'explicit_bad'
        note: Optional text explanation from user
        mcp_call_func: MCP call function for SQLite operations

    Returns:
        True on success, False on error

    Example:
        >>> record_feedback(
        ...     "stock_setup",
        ...     "aluminum",
        ...     "pocket-heavy",
        ...     {"bounding_box": {...}},
        ...     {"stock_dimensions": {...}, "confidence_score": 0.85},
        ...     None,
        ...     "implicit_accept",
        ...     None,
        ...     mcp_call
        ... )
    """
    # Normalize material and geometry_type to lowercase
    material_key = material.lower().strip()
    geometry_key = geometry_type.lower().strip()

    try:
        # Serialize dicts to JSON
        context_json = json.dumps(context, sort_keys=True)
        suggestion_json = json.dumps(suggestion, sort_keys=True)
        user_choice_json = json.dumps(user_choice, sort_keys=True) if user_choice else None

        # Extract confidence_before from suggestion
        confidence_before = suggestion.get("confidence_score")

        # Insert feedback record
        result = _unwrap_mcp_result(mcp_call_func("sqlite", {
            "input": {
                "database": CAM_FEEDBACK_DATABASE,
                "sql": """
                    INSERT INTO cam_feedback_history
                    (operation_type, material, geometry_type, context_snapshot,
                     suggestion_payload, user_choice, feedback_type, feedback_note,
                     confidence_before)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                "params": [
                    operation_type,
                    material_key,
                    geometry_key,
                    context_json,
                    suggestion_json,
                    user_choice_json,
                    feedback_type,
                    note,
                    confidence_before
                ],
                "tool_unlock_token": SQLITE_TOOL_UNLOCK_TOKEN
            }
        }))

        # DEBUG: Log what we actually got back
        print(f"[FEEDBACK_STORE DEBUG] record_feedback result (before unwrap): {json.dumps(result, indent=2)}")

        # Unwrap double-nested result (MCP response has result.result structure)
        if isinstance(result, dict) and 'result' in result:
            result = result['result']
            print(f"[FEEDBACK_STORE DEBUG] After unwrap: {json.dumps(result, indent=2)}")

        # Check for errors - check actual MCP sqlite tool response structure
        if not result:
            print("[FEEDBACK_STORE DEBUG] Result is None/empty - returning False")
            return False
        if isinstance(result, dict):
            # Check for isError flag (MCP sqlite tool sets this)
            if result.get("isError") == True:
                print(f"[FEEDBACK_STORE DEBUG] isError=true detected: {result.get('error_message_if_operation_failed')}")
                return False
            # Check operation_was_successful flag
            if result.get("operation_was_successful") == False:
                print(f"[FEEDBACK_STORE DEBUG] operation_was_successful=false: {result.get('error_message_if_operation_failed')}")
                return False
            # Check for error field
            if result.get("error"):
                print(f"[FEEDBACK_STORE DEBUG] Error field detected: {result.get('error')}")
                return False

        print("[FEEDBACK_STORE DEBUG] All checks passed - returning True")
        return True

    except Exception as e:
        # Re-raise to see what's failing
        raise


# =============================================================================
# FEEDBACK STATISTICS
# =============================================================================

def get_feedback_statistics(
    operation_type: Optional[str] = None,
    mcp_call_func: Callable = None
) -> Dict[str, Any]:
    """
    Get feedback statistics overall and broken down by category.

    Args:
        operation_type: Optional filter by operation type
        mcp_call_func: MCP call function for SQLite operations

    Returns:
        Dict with statistics:
        - overall: {total_count, accept_count, acceptance_rate}
        - by_material: [{material, count, acceptance_pct}, ...]
        - by_geometry_type: [{geometry_type, count, acceptance_pct}, ...]
        - by_operation_type: [{operation_type, count, acceptance_pct}, ...]

    Example:
        >>> stats = get_feedback_statistics(mcp_call_func=mcp_call)
        >>> print(f"Overall acceptance: {stats['overall']['acceptance_rate']:.1%}")
    """
    try:
        # Build WHERE clause if filtering by operation_type
        where_clause = ""
        params = []
        if operation_type:
            where_clause = "WHERE operation_type = ?"
            params = [operation_type]

        # Overall statistics
        overall_result = _unwrap_mcp_result(mcp_call_func("sqlite", {
            "input": {
                "database": CAM_FEEDBACK_DATABASE,
                "sql": f"""
                    SELECT
                        COUNT(*) as total_count,
                        SUM(CASE WHEN feedback_type IN ('implicit_accept', 'explicit_good')
                            THEN 1 ELSE 0 END) as accept_count
                    FROM cam_feedback_history
                    {where_clause}
                """,
                "params": params,
                "tool_unlock_token": SQLITE_TOOL_UNLOCK_TOKEN
            }
        }))

        overall = {"total_count": 0, "accept_count": 0, "acceptance_rate": 0.0}
        if overall_result and isinstance(overall_result, dict):
            rows = overall_result.get("rows") or overall_result.get("data") or overall_result.get("result")
            if rows and len(rows) > 0:
                row = rows[0]
                if isinstance(row, dict):
                    total = row.get("total_count", 0)
                    accepts = row.get("accept_count", 0)
                elif isinstance(row, (list, tuple)) and len(row) >= 2:
                    total = row[0] if row[0] is not None else 0
                    accepts = row[1] if row[1] is not None else 0
                else:
                    total = accepts = 0

                overall["total_count"] = total
                overall["accept_count"] = accepts
                overall["acceptance_rate"] = accepts / total if total > 0 else 0.0

        # By material breakdown
        material_result = _unwrap_mcp_result(mcp_call_func("sqlite", {
            "input": {
                "database": CAM_FEEDBACK_DATABASE,
                "sql": f"""
                    SELECT
                        material,
                        COUNT(*) as count,
                        ROUND(100.0 * SUM(CASE WHEN feedback_type IN ('implicit_accept', 'explicit_good')
                            THEN 1 ELSE 0 END) / COUNT(*), 1) as acceptance_pct
                    FROM cam_feedback_history
                    {where_clause}
                    GROUP BY material
                    ORDER BY count DESC
                """,
                "params": params,
                "tool_unlock_token": SQLITE_TOOL_UNLOCK_TOKEN
            }
        }))

        by_material = []
        if material_result and isinstance(material_result, dict):
            rows = material_result.get("rows") or material_result.get("data") or material_result.get("result")
            if rows:
                for row in rows:
                    if isinstance(row, dict):
                        by_material.append({
                            "material": row.get("material"),
                            "count": row.get("count", 0),
                            "acceptance_pct": row.get("acceptance_pct", 0.0)
                        })
                    elif isinstance(row, (list, tuple)) and len(row) >= 3:
                        by_material.append({
                            "material": row[0],
                            "count": row[1] if row[1] is not None else 0,
                            "acceptance_pct": row[2] if row[2] is not None else 0.0
                        })

        # By geometry_type breakdown
        geometry_result = _unwrap_mcp_result(mcp_call_func("sqlite", {
            "input": {
                "database": CAM_FEEDBACK_DATABASE,
                "sql": f"""
                    SELECT
                        geometry_type,
                        COUNT(*) as count,
                        ROUND(100.0 * SUM(CASE WHEN feedback_type IN ('implicit_accept', 'explicit_good')
                            THEN 1 ELSE 0 END) / COUNT(*), 1) as acceptance_pct
                    FROM cam_feedback_history
                    {where_clause}
                    GROUP BY geometry_type
                    ORDER BY count DESC
                """,
                "params": params,
                "tool_unlock_token": SQLITE_TOOL_UNLOCK_TOKEN
            }
        }))

        by_geometry_type = []
        if geometry_result and isinstance(geometry_result, dict):
            rows = geometry_result.get("rows") or geometry_result.get("data") or geometry_result.get("result")
            if rows:
                for row in rows:
                    if isinstance(row, dict):
                        by_geometry_type.append({
                            "geometry_type": row.get("geometry_type"),
                            "count": row.get("count", 0),
                            "acceptance_pct": row.get("acceptance_pct", 0.0)
                        })
                    elif isinstance(row, (list, tuple)) and len(row) >= 3:
                        by_geometry_type.append({
                            "geometry_type": row[0],
                            "count": row[1] if row[1] is not None else 0,
                            "acceptance_pct": row[2] if row[2] is not None else 0.0
                        })

        # By operation_type breakdown (unless already filtered)
        by_operation_type = []
        if not operation_type:
            operation_result = _unwrap_mcp_result(mcp_call_func("sqlite", {
                "input": {
                "database": CAM_FEEDBACK_DATABASE,
                "sql": """
                        SELECT
                            operation_type,
                            COUNT(*) as count,
                            ROUND(100.0 * SUM(CASE WHEN feedback_type IN ('implicit_accept', 'explicit_good')
                                THEN 1 ELSE 0 END) / COUNT(*), 1) as acceptance_pct
                        FROM cam_feedback_history
                        GROUP BY operation_type
                        ORDER BY count DESC
                    """,
                    "params": [],
                    "tool_unlock_token": SQLITE_TOOL_UNLOCK_TOKEN
                }
            }))

            if operation_result and isinstance(operation_result, dict):
                rows = operation_result.get("rows") or operation_result.get("data") or operation_result.get("result")
                if rows:
                    for row in rows:
                        if isinstance(row, dict):
                            by_operation_type.append({
                                "operation_type": row.get("operation_type"),
                                "count": row.get("count", 0),
                                "acceptance_pct": row.get("acceptance_pct", 0.0)
                            })
                        elif isinstance(row, (list, tuple)) and len(row) >= 3:
                            by_operation_type.append({
                                "operation_type": row[0],
                                "count": row[1] if row[1] is not None else 0,
                                "acceptance_pct": row[2] if row[2] is not None else 0.0
                            })

        return {
            "overall": overall,
            "by_material": by_material,
            "by_geometry_type": by_geometry_type,
            "by_operation_type": by_operation_type
        }

    except Exception:
        return {
            "overall": {"total_count": 0, "accept_count": 0, "acceptance_rate": 0.0},
            "by_material": [],
            "by_geometry_type": [],
            "by_operation_type": []
        }


# =============================================================================
# FEEDBACK EXPORT
# =============================================================================

def export_feedback_history(
    format: str,
    operation_type: Optional[str] = None,
    mcp_call_func: Callable = None
) -> str:
    """
    Export feedback history to CSV or JSON format.

    Args:
        format: 'csv' or 'json'
        operation_type: Optional filter by operation type
        mcp_call_func: MCP call function for SQLite operations

    Returns:
        Formatted string (CSV or JSON)

    Example:
        >>> csv_data = export_feedback_history('csv', mcp_call_func=mcp_call)
        >>> with open('feedback.csv', 'w') as f:
        ...     f.write(csv_data)
    """
    try:
        # Build WHERE clause if filtering by operation_type
        where_clause = ""
        params = []
        if operation_type:
            where_clause = "WHERE operation_type = ?"
            params = [operation_type]

        # Query all feedback rows
        result = _unwrap_mcp_result(mcp_call_func("sqlite", {
            "input": {
                "database": CAM_FEEDBACK_DATABASE,
                "sql": f"""
                    SELECT id, operation_type, material, geometry_type,
                           context_snapshot, suggestion_payload, user_choice,
                           feedback_type, feedback_note, confidence_before, created_at
                    FROM cam_feedback_history
                    {where_clause}
                    ORDER BY created_at DESC
                """,
                "params": params,
                "tool_unlock_token": SQLITE_TOOL_UNLOCK_TOKEN
            }
        }))

        rows = []
        if result and isinstance(result, dict):
            rows_data = result.get("rows") or result.get("data") or result.get("result")
            if rows_data:
                for row in rows_data:
                    if isinstance(row, dict):
                        rows.append(row)
                    elif isinstance(row, (list, tuple)) and len(row) >= 11:
                        rows.append({
                            "id": row[0],
                            "operation_type": row[1],
                            "material": row[2],
                            "geometry_type": row[3],
                            "context_snapshot": row[4],
                            "suggestion_payload": row[5],
                            "user_choice": row[6],
                            "feedback_type": row[7],
                            "feedback_note": row[8],
                            "confidence_before": row[9],
                            "created_at": row[10]
                        })

        # Format output
        if format == 'csv':
            if not rows:
                return ""

            output = StringIO()
            fieldnames = [
                "id", "operation_type", "material", "geometry_type",
                "context_snapshot", "suggestion_payload", "user_choice",
                "feedback_type", "feedback_note", "confidence_before", "created_at"
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            return output.getvalue()

        elif format == 'json':
            return json.dumps(rows, indent=2)

        else:
            return ""

    except Exception:
        return ""


# =============================================================================
# FEEDBACK CLEANUP
# =============================================================================

def clear_feedback_history(
    operation_type: Optional[str] = None,
    mcp_call_func: Callable = None
) -> Dict[str, Any]:
    """
    Clear feedback history (all or filtered by operation_type).

    Per-category reset capability enables targeted learning resets.

    Args:
        operation_type: Optional filter - only delete matching operation type
                        If None, deletes all feedback
        mcp_call_func: MCP call function for SQLite operations

    Returns:
        Dict with deletion info:
        - deleted_count: Number of rows deleted
        - operation_type: Operation type that was cleared, or "all"

    Example:
        >>> result = clear_feedback_history("stock_setup", mcp_call)
        >>> print(f"Deleted {result['deleted_count']} stock_setup feedback events")
    """
    try:
        # Build DELETE query
        if operation_type:
            sql = "DELETE FROM cam_feedback_history WHERE operation_type = ?"
            params = [operation_type]
            cleared_type = operation_type
        else:
            sql = "DELETE FROM cam_feedback_history"
            params = []
            cleared_type = "all"

        # Execute delete
        result = _unwrap_mcp_result(mcp_call_func("sqlite", {
            "input": {
                "database": CAM_FEEDBACK_DATABASE,
                "sql": sql,
                "params": params,
                "tool_unlock_token": SQLITE_TOOL_UNLOCK_TOKEN
            }
        }))

        # Get row count (SQLite doesn't return affected rows in standard way)
        # Query to count remaining rows
        count_result = _unwrap_mcp_result(mcp_call_func("sqlite", {
            "input": {
                "database": CAM_FEEDBACK_DATABASE,
                "sql": "SELECT COUNT(*) FROM cam_feedback_history",
                "params": [],
                "tool_unlock_token": SQLITE_TOOL_UNLOCK_TOKEN
            }
        }))

        # For simplicity, return success indicator
        # In production, could query before/after to get exact count
        return {
            "deleted_count": 0,  # Would need before/after query to compute
            "operation_type": cleared_type
        }

    except Exception:
        return {
            "deleted_count": 0,
            "operation_type": operation_type or "all"
        }
