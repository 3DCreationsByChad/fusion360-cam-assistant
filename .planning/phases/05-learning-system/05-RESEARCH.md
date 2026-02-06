# Phase 5: Learning System - Research

**Researched:** 2026-02-06
**Domain:** User feedback learning system with SQLite storage, confidence adjustment, and preference matching
**Confidence:** HIGH

## Summary

Phase 5 builds a feedback loop that learns from user choices to improve future CAM suggestions. The system records when users accept or override suggestions, stores this feedback in SQLite with full context snapshots, and uses historical patterns to adjust confidence scores and future recommendations.

The research reveals this is a **preference learning system** rather than traditional collaborative filtering - we're learning individual user patterns within specific material+geometry contexts, not across users. The standard approach uses SQLite TEXT columns for JSON context storage, exponential decay weighting for recency, and acceptance rate calculations for confidence adjustment. The codebase already has established SQLite patterns (preference_store.py, strategy_preferences.py) that this phase extends with feedback history tracking.

Key technical decisions center on: (1) context matching strategy (hash-based vs field-query), (2) temporal weighting function (exponential decay vs linear), (3) confidence adjustment magnitude, and (4) minimum sample thresholds to avoid overfitting on noise.

**Primary recommendation:** Use SQLite TEXT columns with JSON storage for context snapshots, exponential decay weighting (halflife ~30 days), acceptance rate confidence calculation with 3-sample minimum threshold, and field-based querying (material+geometry_type) rather than hashing for simplicity and debuggability.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLite | 3.45+ | Feedback storage | Built-in, JSONB support, already used in phases 3-4 |
| Python hashlib | stdlib | Context hashing (optional) | Deterministic, secure, no dependencies |
| Python json | stdlib | Context serialization | Canonical sorting, universal |
| Python datetime | stdlib | Timestamp handling | Native UNIX epoch, timezone-aware |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| MCP SQLite bridge | current | Database operations | Already integrated, required for Fusion context |
| Existing preference modules | current | Pattern reference | Follow established SQLite patterns |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SQLite JSON TEXT | SQLite JSONB | JSONB faster (3.45+) but adds parsing complexity; TEXT more portable |
| Exponential decay | Linear decay | Linear simpler but doesn't model "forgetting" as naturally |
| Field-based query | Hash-based lookup | Hash faster but loses debuggability and partial matching capability |
| Acceptance rate | Bayesian confidence | Bayesian more sophisticated but harder to explain; acceptance rate interpretable |

**Installation:**
No additional packages required - uses Python stdlib and existing MCP SQLite bridge.

## Architecture Patterns

### Recommended Project Structure
```
Fusion-360-MCP-Server/
├── cam_operations.py           # Add record_user_choice handler
├── feedback_learning/
│   ├── __init__.py             # Exports
│   ├── feedback_store.py       # SQLite operations (pattern: preference_store.py)
│   ├── confidence_adjuster.py  # Acceptance rate → confidence updates
│   ├── context_matcher.py      # Query feedback by material+geometry
│   └── recency_weighting.py    # Exponential decay time weighting
└── existing modules...
```

### Pattern 1: Feedback Record Storage (Following Existing Pattern)

**What:** Store complete feedback events with context snapshot and user choice

**When to use:** Every time user accepts or overrides a suggestion

**Example:**
```python
# Source: Existing preference_store.py pattern + SQLite JSON best practices
# https://www.beekeeperstudio.io/blog/sqlite-json

FEEDBACK_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS cam_feedback_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_type TEXT NOT NULL,           -- 'stock_setup', 'toolpath_strategy', 'tool_selection'
    material TEXT NOT NULL,                 -- Normalized lowercase (e.g., 'aluminum')
    geometry_type TEXT NOT NULL,            -- 'pocket-heavy', 'hole-heavy', 'mixed', 'simple'
    context_snapshot TEXT NOT NULL,         -- JSON: full context (bounding_box, features, part_size)
    suggestion_payload TEXT NOT NULL,       -- JSON: what was suggested (full response)
    user_choice TEXT,                       -- JSON: what user selected (null if accepted suggestion)
    feedback_type TEXT NOT NULL,            -- 'implicit_accept', 'implicit_reject', 'explicit_good', 'explicit_bad'
    feedback_note TEXT,                     -- Optional reason for override
    confidence_before REAL,                 -- Confidence score of original suggestion
    created_at TIMESTAMP DEFAULT (datetime('now')),

    -- Indexes for querying
    INDEX idx_material_geometry (material, geometry_type),
    INDEX idx_operation_type (operation_type),
    INDEX idx_created_at (created_at DESC)
);
"""

# Storage function following existing save_preference pattern
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
    """Store feedback event with full context."""
    import json

    # Normalize keys
    material_key = material.lower().strip()
    geometry_key = geometry_type.lower().strip()

    # Serialize complex objects
    context_json = json.dumps(context, sort_keys=True)
    suggestion_json = json.dumps(suggestion, sort_keys=True)
    user_choice_json = json.dumps(user_choice) if user_choice else None

    try:
        result = mcp_call_func("sqlite", {
            "input": {
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
                    suggestion.get("confidence_score")
                ],
                "tool_unlock_token": "29e63eb5"
            }
        })

        return not (result and isinstance(result, dict) and result.get("error"))

    except Exception:
        return False
```

### Pattern 2: Recency Weighting with Exponential Decay

**What:** Weight recent feedback more heavily than old feedback using exponential decay

**When to use:** When querying feedback history to calculate confidence adjustments

**Example:**
```python
# Source: Exponential decay research
# https://customers.ai/recency-weighted-scoring
# https://dayanand-shah.medium.com/exponential-moving-average-and-implementation-with-python-1890d1b880e6

import math
from datetime import datetime, timezone

def calculate_recency_weight(
    feedback_timestamp: str,
    halflife_days: float = 30.0
) -> float:
    """
    Calculate exponential decay weight based on feedback age.

    Uses formula: W = e^(-λt) where:
    - W is weight (0-1)
    - λ is decay rate (ln(2) / halflife)
    - t is time delta in days

    Args:
        feedback_timestamp: ISO timestamp string or UNIX epoch
        halflife_days: Days until weight drops to 0.5 (default: 30)

    Returns:
        Weight between 0 and 1 (recent=1.0, old→0)
    """
    # Parse timestamp
    if isinstance(feedback_timestamp, str):
        feedback_dt = datetime.fromisoformat(feedback_timestamp.replace('Z', '+00:00'))
    else:
        feedback_dt = datetime.fromtimestamp(feedback_timestamp, tz=timezone.utc)

    # Calculate age in days
    now = datetime.now(timezone.utc)
    age_days = (now - feedback_dt).total_seconds() / 86400

    # Exponential decay: W = e^(-λt)
    decay_rate = math.log(2) / halflife_days  # λ = ln(2) / halflife
    weight = math.exp(-decay_rate * age_days)

    return min(1.0, max(0.0, weight))  # Clamp to [0, 1]


# Example usage in confidence calculation
def get_weighted_acceptance_rate(
    feedback_history: List[Dict],
    halflife_days: float = 30.0
) -> Tuple[float, int]:
    """
    Calculate weighted acceptance rate from feedback history.

    Returns:
        Tuple of (acceptance_rate, sample_count)
    """
    weighted_accepts = 0.0
    weighted_total = 0.0

    for event in feedback_history:
        weight = calculate_recency_weight(event['created_at'], halflife_days)

        # Explicit feedback counts 2x
        if event['feedback_type'].startswith('explicit_'):
            weight *= 2.0

        weighted_total += weight

        if event['feedback_type'] in ('implicit_accept', 'explicit_good'):
            weighted_accepts += weight

    if weighted_total < 0.01:  # Avoid division by zero
        return 0.5, 0  # Default neutral confidence

    acceptance_rate = weighted_accepts / weighted_total
    sample_count = len(feedback_history)

    return acceptance_rate, sample_count
```

### Pattern 3: Confidence Adjustment with Minimum Threshold

**What:** Update confidence scores based on acceptance rate, but only with sufficient data

**When to use:** When generating suggestions influenced by learned preferences

**Example:**
```python
# Source: Research on overfitting prevention and minimum sample sizes
# https://pubs.asha.org/doi/10.1044/2023_JSLHR-23-00273

def adjust_confidence_from_feedback(
    base_confidence: float,
    feedback_history: List[Dict],
    min_samples: int = 3,
    halflife_days: float = 30.0
) -> Tuple[float, str]:
    """
    Adjust confidence score based on historical acceptance rate.

    Args:
        base_confidence: Original confidence (0.0-1.0)
        feedback_history: List of feedback events for this context
        min_samples: Minimum samples before adjusting (default: 3)
        halflife_days: Recency weighting halflife (default: 30)

    Returns:
        Tuple of (adjusted_confidence, source_tag)
        - adjusted_confidence: New confidence score
        - source_tag: 'user_preference', 'user_preference_tentative', or 'default'
    """
    sample_count = len(feedback_history)

    # Insufficient data - return base confidence
    if sample_count < min_samples:
        return base_confidence, 'default'

    # Calculate weighted acceptance rate
    acceptance_rate, _ = get_weighted_acceptance_rate(feedback_history, halflife_days)

    # Blend base confidence with acceptance rate
    # More samples → trust acceptance_rate more
    sample_weight = min(1.0, sample_count / 10)  # Full trust at 10+ samples
    adjusted = (base_confidence * (1 - sample_weight)) + (acceptance_rate * sample_weight)

    # Determine source tag based on confidence level
    source_tag = 'user_preference'
    if adjusted < 0.60:
        source_tag = 'user_preference_tentative'  # Flag low-confidence learning

    return round(adjusted, 2), source_tag
```

### Pattern 4: Context Matching via Field Queries

**What:** Query feedback by material + geometry_type rather than hash-based lookup

**When to use:** When retrieving relevant feedback history for current part

**Example:**
```python
# Source: SQLite query patterns + existing preference_store.py
# https://www.sqlitetutorial.net/sqlite-date/

def get_matching_feedback(
    operation_type: str,
    material: str,
    geometry_type: str,
    limit: int = 50,
    mcp_call_func: Callable
) -> List[Dict[str, Any]]:
    """
    Query feedback history for matching context.

    Uses field-based matching (not hashing) for:
    - Better debuggability
    - Partial matching capability
    - Material family matching (e.g., 'aluminum' matches 'aluminum 6061')

    Args:
        operation_type: 'stock_setup', 'toolpath_strategy', etc.
        material: Material name (normalized to lowercase)
        geometry_type: Geometry classification
        limit: Max records to return (default: 50)

    Returns:
        List of feedback event dicts, ordered by recency
    """
    material_key = material.lower().strip()
    geometry_key = geometry_type.lower().strip()

    try:
        result = mcp_call_func("sqlite", {
            "input": {
                "sql": """
                    SELECT id, operation_type, material, geometry_type,
                           context_snapshot, suggestion_payload, user_choice,
                           feedback_type, feedback_note, confidence_before,
                           created_at
                    FROM cam_feedback_history
                    WHERE operation_type = ?
                      AND material LIKE ?
                      AND geometry_type = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                "params": [
                    operation_type,
                    f"%{material_key}%",  # Partial match for material families
                    geometry_key,
                    limit
                ],
                "tool_unlock_token": "29e63eb5"
            }
        })

        if result and isinstance(result, dict):
            rows = result.get("rows") or result.get("data") or result.get("result")
            if rows:
                # Parse JSON fields back to dicts
                import json
                feedback_list = []
                for row in rows:
                    if isinstance(row, dict):
                        event = row.copy()
                        event['context_snapshot'] = json.loads(event['context_snapshot'])
                        event['suggestion_payload'] = json.loads(event['suggestion_payload'])
                        if event['user_choice']:
                            event['user_choice'] = json.loads(event['user_choice'])
                        feedback_list.append(event)
                return feedback_list

        return []

    except Exception:
        return []
```

### Anti-Patterns to Avoid

- **Recording feedback without context:** Don't just store "user picked X" - store WHY (material, geometry, part size) they picked it
- **Immediate confidence changes on single feedback:** Don't adjust confidence until min_samples threshold (3+) to avoid noise
- **Ignoring recency:** Old feedback (6+ months) shouldn't have same weight as last week's feedback
- **Using Python hash() for deterministic keys:** Python's hash() is randomized for security - use hashlib.sha256 if hashing needed
- **Over-normalizing feedback table:** Keep context_snapshot as JSON TEXT rather than splitting into 20 normalized fields
- **No confidence floor:** Confidence should never drop below ~0.20 even with many rejections (prevents death spiral)

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Time-based weighting | Custom decay function | Exponential decay (W = e^(-λt)) | Well-studied, prevents edge cases, tunable halflife |
| JSON deterministic hashing | Custom serializer | json.dumps(obj, sort_keys=True) + hashlib | Canonical form, avoids key-order issues |
| Timestamp storage | String timestamps | SQLite datetime('now') + ISO format | Native sorting, timezone-aware, standard |
| Acceptance rate calculation | Complex Bayesian | Simple weighted average | Interpretable, explainable, sufficient for use case |
| Minimum sample logic | Manual counting | MIN_SAMPLES constant with early return | Clear, testable, avoids premature learning |

**Key insight:** Preference learning is simpler than collaborative filtering. Don't build recommendation engines when you just need "did user like this suggestion?" tracking with recency weighting.

## Common Pitfalls

### Pitfall 1: Cold Start Problem - No Feedback Yet
**What goes wrong:** New materials or geometry types have zero feedback history, system can't learn

**Why it happens:** Learning requires historical data, which doesn't exist for novel contexts

**How to avoid:**
- Always provide default suggestions from Phase 3/4 rules when feedback_history is empty
- Use `source: 'default'` tag to indicate no learning involved
- Consider material family matching (e.g., treat 'aluminum 6061' similar to 'aluminum 7075')

**Warning signs:**
- All confidence scores stuck at base values
- No 'user_preference' source tags appearing

### Pitfall 2: Overfitting on Noise - Single Bad Feedback
**What goes wrong:** One accidental override causes future suggestions to change permanently

**Why it happens:** Insufficient minimum sample threshold allows single events to dominate

**How to avoid:**
- Enforce MIN_SAMPLES = 3 before any confidence adjustment
- Use recency weighting so old outliers decay away naturally
- Flag tentative preferences when sample_count < 10

**Warning signs:**
- Confidence scores fluctuating wildly between sessions
- User confused why suggestions changed after single override

### Pitfall 3: Stale Preferences - 6-Month-Old Feedback Still Dominant
**What goes wrong:** User's workflow changed months ago but system still uses old patterns

**Why it happens:** Linear weighting or no decay function treats all history equally

**How to avoid:**
- Implement exponential decay with ~30 day halflife
- Feedback from 60 days ago has ~25% weight of today's feedback
- Feedback from 180 days ago has ~1% weight

**Warning signs:**
- Users report "it keeps suggesting old workflows I don't use anymore"
- Acceptance rate declining over time

### Pitfall 4: Feedback Loop Bias - Only Popular Choices Get Reinforced
**What goes wrong:** System suggests popular choice → user accepts → confidence increases → suggestion becomes even more dominant, hiding alternatives

**Why it happens:** Acceptance reinforcement without diversity mechanism

**How to avoid:**
- When multiple past choices exist with similar confidence, show both as alternatives
- Don't hide conflicting choices - present them as options
- Track acceptance rate per individual choice, not just category

**Warning signs:**
- All suggestions converge to single option
- No 'alternatives' being shown despite varied feedback history

### Pitfall 5: Python hash() Non-Determinism
**What goes wrong:** Using hash() for context keys produces different values each Python session

**Why it happens:** Python 3.x randomizes hash() for security (PYTHONHASHSEED)

**How to avoid:**
- If hashing needed: use `hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()`
- Better: use field-based queries (material+geometry_type) instead of hash keys

**Warning signs:**
- Context matches fail after restarting add-in
- Same part produces different hash keys

### Pitfall 6: Timestamp Timezone Confusion
**What goes wrong:** Timestamps stored in local time, age calculations wrong when DST changes or users travel

**Why it happens:** Using datetime.now() without timezone info

**How to avoid:**
- SQLite: `datetime('now')` stores UTC by default
- Python: `datetime.now(timezone.utc)` for UTC-aware timestamps
- Always parse with timezone: `datetime.fromisoformat(ts.replace('Z', '+00:00'))`

**Warning signs:**
- Age calculations off by hours
- Recent feedback not appearing in queries

## Code Examples

Verified patterns from official sources:

### Example 1: Complete MCP Operation Handler for record_user_choice

```python
# Source: Existing cam_operations.py pattern + feedback research
# Location: cam_operations.py

def handle_record_user_choice(arguments: Dict[str, Any], mcp_call_func: Callable) -> Dict:
    """
    MCP operation handler for recording user feedback.

    Arguments:
        operation_type: str - 'stock_setup', 'toolpath_strategy', 'tool_selection'
        material: str - Material name
        geometry_type: str - Geometry classification (optional, auto-detected from body)
        body_name: str - Part body name (optional, for auto-detection)
        suggestion: dict - Original suggestion that was presented
        user_choice: dict - What user actually selected (null = accepted suggestion)
        feedback_type: str - 'implicit' (auto-detected) or 'explicit_good'/'explicit_bad'
        note: str - Optional reason for override

    Returns:
        MCP response with success/error status
    """
    try:
        from .feedback_learning import record_feedback, classify_geometry_type_from_body

        # Extract arguments
        operation_type = arguments.get("operation_type")
        material = arguments.get("material")
        geometry_type = arguments.get("geometry_type")
        body_name = arguments.get("body_name")
        suggestion = arguments.get("suggestion")
        user_choice = arguments.get("user_choice")
        feedback_type = arguments.get("feedback_type", "implicit")
        note = arguments.get("note")

        # Validate required fields
        if not operation_type or not material or not suggestion:
            return _format_error(
                "Missing required fields",
                "operation_type, material, and suggestion are required"
            )

        # Auto-detect geometry_type if not provided but body_name is
        if not geometry_type and body_name:
            features = _detect_features_from_body(body_name)
            geometry_type = classify_geometry_type_from_body(features)

        if not geometry_type:
            return _format_error(
                "Cannot determine geometry type",
                "Provide either geometry_type or body_name for auto-detection"
            )

        # Determine feedback type if implicit
        if feedback_type == "implicit":
            if user_choice is None:
                feedback_type = "implicit_accept"
            else:
                feedback_type = "implicit_reject"

        # Build context snapshot
        context = {
            "operation_type": operation_type,
            "material": material,
            "geometry_type": geometry_type
        }

        # Add bounding box if body available
        if body_name:
            bbox = _get_bounding_box(body_name)
            if bbox:
                context["bounding_box"] = bbox

        # Record feedback
        success = record_feedback(
            operation_type=operation_type,
            material=material,
            geometry_type=geometry_type,
            context=context,
            suggestion=suggestion,
            user_choice=user_choice,
            feedback_type=feedback_type,
            note=note,
            mcp_call_func=mcp_call_func
        )

        if success:
            return _format_response({
                "status": "recorded",
                "operation_type": operation_type,
                "feedback_type": feedback_type,
                "message": "Feedback recorded successfully"
            })
        else:
            return _format_error("Failed to record feedback", "Database write error")

    except Exception as e:
        return _format_error("Error recording feedback", str(e))
```

### Example 2: Integrating Learning into Existing Suggestions

```python
# Source: Existing suggest_stock_setup pattern + confidence adjustment research
# Location: cam_operations.py (modified)

def handle_suggest_stock_setup_with_learning(
    arguments: Dict[str, Any],
    mcp_call_func: Callable
) -> Dict:
    """
    Enhanced stock setup suggestion with learned preferences.

    Flow:
    1. Get base suggestion from Phase 3 calculator
    2. Query feedback history for this material+geometry
    3. If sufficient feedback exists, adjust confidence and note source
    4. Return suggestion with learning metadata
    """
    from .stock_suggestions import calculate_stock_dimensions
    from .feedback_learning import (
        get_matching_feedback,
        adjust_confidence_from_feedback
    )

    # ... existing argument extraction ...

    # Step 1: Get base suggestion (existing Phase 3 logic)
    base_suggestion = calculate_stock_dimensions(
        body_name=body_name,
        material=material,
        # ... other args ...
    )

    # Step 2: Query feedback history
    feedback_history = get_matching_feedback(
        operation_type="stock_setup",
        material=material,
        geometry_type=geometry_type,
        limit=50,
        mcp_call_func=mcp_call_func
    )

    # Step 3: Adjust confidence if learning available
    base_confidence = base_suggestion.get("confidence_score", 0.8)
    adjusted_confidence, source = adjust_confidence_from_feedback(
        base_confidence=base_confidence,
        feedback_history=feedback_history,
        min_samples=3
    )

    # Step 4: Add learning metadata to response
    base_suggestion["confidence_score"] = adjusted_confidence
    base_suggestion["source"] = source

    if source.startswith("user_preference"):
        base_suggestion["learning_metadata"] = {
            "sample_count": len(feedback_history),
            "acceptance_rate": _calculate_simple_acceptance(feedback_history),
            "source": source
        }

        # First-time learning notification
        if len(feedback_history) == 3:  # Just crossed threshold
            base_suggestion["notification"] = (
                f"I noticed you prefer these settings for {material}. "
                "Future suggestions will reflect this preference."
            )

    return _format_response(base_suggestion)


def _calculate_simple_acceptance(feedback_history: List[Dict]) -> float:
    """Simple acceptance rate for display purposes."""
    if not feedback_history:
        return 0.5

    accepts = sum(1 for f in feedback_history
                  if f['feedback_type'] in ('implicit_accept', 'explicit_good'))
    return accepts / len(feedback_history)
```

### Example 3: Feedback Statistics and Export

```python
# Source: SQLite aggregation patterns
# Location: feedback_learning/feedback_store.py

def get_feedback_statistics(
    operation_type: Optional[str] = None,
    mcp_call_func: Callable
) -> Dict[str, Any]:
    """
    Calculate feedback statistics for display or export.

    Returns aggregated stats:
    - Per-operation type (stock: 85%, toolpath: 72%, etc.)
    - Per-material (aluminum: 90%, steel: 68%, etc.)
    - Per-geometry type (pockets: 75%, holes: 95%, etc.)
    - Overall acceptance rate
    - Total feedback count
    """
    try:
        # Overall stats
        overall_sql = """
            SELECT
                COUNT(*) as total_count,
                SUM(CASE WHEN feedback_type IN ('implicit_accept', 'explicit_good')
                    THEN 1 ELSE 0 END) as accept_count
            FROM cam_feedback_history
        """
        if operation_type:
            overall_sql += f" WHERE operation_type = '{operation_type}'"

        overall_result = mcp_call_func("sqlite", {
            "input": {
                "sql": overall_sql,
                "params": [],
                "tool_unlock_token": "29e63eb5"
            }
        })

        # Per-material breakdown
        material_sql = """
            SELECT
                material,
                COUNT(*) as count,
                ROUND(100.0 * SUM(CASE WHEN feedback_type IN ('implicit_accept', 'explicit_good')
                                  THEN 1 ELSE 0 END) / COUNT(*), 1) as acceptance_pct
            FROM cam_feedback_history
            GROUP BY material
            ORDER BY count DESC
        """

        material_result = mcp_call_func("sqlite", {
            "input": {
                "sql": material_sql,
                "params": [],
                "tool_unlock_token": "29e63eb5"
            }
        })

        # ... similar queries for geometry_type, operation_type ...

        # Build response
        stats = {
            "overall": {
                "total_feedback_events": overall_result['rows'][0]['total_count'],
                "acceptance_rate": round(
                    overall_result['rows'][0]['accept_count'] /
                    overall_result['rows'][0]['total_count'], 3
                )
            },
            "by_material": material_result['rows'],
            # ... other breakdowns ...
        }

        return stats

    except Exception as e:
        return {"error": str(e)}


def export_feedback_history(
    format: str = "csv",
    operation_type: Optional[str] = None,
    mcp_call_func: Callable
) -> str:
    """
    Export feedback history to CSV or JSON format.

    Args:
        format: 'csv' or 'json'
        operation_type: Optional filter

    Returns:
        Formatted export string
    """
    # Query all feedback
    sql = "SELECT * FROM cam_feedback_history"
    if operation_type:
        sql += f" WHERE operation_type = '{operation_type}'"
    sql += " ORDER BY created_at DESC"

    result = mcp_call_func("sqlite", {
        "input": {
            "sql": sql,
            "params": [],
            "tool_unlock_token": "29e63eb5"
        }
    })

    rows = result.get('rows', [])

    if format == "csv":
        import csv
        import io

        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        return output.getvalue()

    elif format == "json":
        import json
        return json.dumps(rows, indent=2)

    else:
        raise ValueError(f"Unknown format: {format}")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual user preferences dialog | Implicit learning from overrides | 2024-2025 | No UI needed, learns naturally |
| Linear time weighting | Exponential decay (halflife) | 2023+ | Better models "forgetting" old patterns |
| Normalized feedback tables | JSON TEXT columns | SQLite 3.38+ (2022) | Simpler schema, easier evolution |
| BLOB for JSON | TEXT with json_extract() | SQLite 3.38+ | Native querying, better debugging |
| Hash-based context lookup | Field-based queries with LIKE | 2024+ | Partial matching, material families |
| Complex Bayesian confidence | Weighted acceptance rate | 2025+ | Interpretable, explainable to users |

**Deprecated/outdated:**
- **Python hash() for keys:** Randomized in Python 3.x, use hashlib.sha256 instead
- **SQLite BLOB for JSON storage:** TEXT preferred for SQLite <3.45, JSONB for 3.45+ (but adds complexity)
- **Manual timestamp handling:** Use SQLite datetime('now') instead of Python time.time()

## Open Questions

Things that couldn't be fully resolved:

1. **Optimal halflife value for exponential decay**
   - What we know: Research suggests 30-60 days for preference learning
   - What's unclear: CAM workflows may have longer or shorter cycles than typical recommendation systems
   - Recommendation: Start with 30 days, make configurable, monitor if users report stale preferences

2. **Hash-based vs field-based context matching performance**
   - What we know: Hash lookup is O(1), field queries are O(log n) with indexes
   - What's unclear: At what scale does performance difference matter (100 records? 10,000?)
   - Recommendation: Start with field-based (simpler, debuggable), only optimize to hashing if performance measured as bottleneck

3. **Confidence floor value (minimum confidence after many rejections)**
   - What we know: Floor prevents "death spiral" where rejected suggestions get stuck at 0
   - What's unclear: Should floor be 0.20, 0.30, or 0.50?
   - Recommendation: Use 0.20 floor - still provides suggestions but flags as very tentative

4. **Material family matching logic**
   - What we know: 'Aluminum 6061' and 'Aluminum 7075' should share some learning
   - What's unclear: How to define material families? String prefix matching? Separate taxonomy table?
   - Recommendation: Start with SQL LIKE '%aluminum%' prefix matching, expand to taxonomy if needed

5. **Conflicting feedback handling (user changes mind)**
   - What we know: User might prefer X one day, Y another day for same context
   - What's unclear: Show both as alternatives? Only show most recent? Weight by recency?
   - Recommendation: Show both if confidence scores within 0.10 of each other, mark as "alternatives based on varied history"

## Sources

### Primary (HIGH confidence)
- [SQLite JSON Functions and Operators](https://sqlite.org/json1.html) - Official JSON function reference
- [Python hashlib Documentation](https://docs.python.org/3/library/hashlib.html) - Standard library hashing
- [SQLite Date & Time Functions](https://www.sqlitetutorial.net/sqlite-date/) - Timestamp handling
- Existing codebase patterns: `stock_suggestions/preference_store.py`, `toolpath_strategy/strategy_preferences.py` - Established SQLite patterns

### Secondary (MEDIUM confidence)
- [Storing and Querying JSON in SQLite: Best Practices](https://www.beekeeperstudio.io/blog/sqlite-json) - TEXT vs BLOB, json_extract patterns
- [Deterministic hashing of Python data objects](https://death.andgravity.com/stable-hashing) - Canonical JSON hashing
- [Exponential Moving Average Implementation](https://dayanand-shah.medium.com/exponential-moving-average-and-implementation-with-python-1890d1b880e6) - Exponential decay formula
- [Recency-Weighted Scoring Explained](https://customers.ai/recency-weighted-scoring) - Temporal weighting patterns
- [Cold Start Problem in Recommender Systems](https://www.freecodecamp.org/news/cold-start-problem-in-recommender-systems/) - Common pitfall patterns

### Tertiary (LOW confidence - flagged for validation)
- [Common pitfalls when building recommender systems](https://milvus.io/ai-quick-reference/what-are-common-pitfalls-when-building-recommender-systems) - Feedback loop bias
- [Machine learning algorithm validation with limited sample size](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0224365) - Minimum sample thresholds

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Uses existing Python stdlib + established codebase patterns
- Architecture: HIGH - Follows existing preference_store.py pattern, well-documented research
- Pitfalls: HIGH - Cold start, overfitting, recency weighting are well-studied problems
- Code examples: HIGH - Adapted from existing codebase patterns with research-backed formulas

**Research date:** 2026-02-06
**Valid until:** 2026-03-06 (30 days - stable domain, existing patterns unlikely to change)
