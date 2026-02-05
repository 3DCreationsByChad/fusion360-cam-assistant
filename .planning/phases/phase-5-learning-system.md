# Phase 5: Learning System

## Goal

Learn from user choices to improve future suggestions.

## Success Criteria

- [ ] `record_user_choice` stores feedback
- [ ] Feedback history table tracks all suggestions
- [ ] Confidence scores update based on acceptance
- [ ] Learned preferences influence suggestions

## Tasks

### 5.1 Implement record_user_choice

**Input:**
```json
{
  "operation": "record_user_choice",
  "context": {
    "geometry_hash": "abc123def456",
    "material": "aluminum_6061",
    "feature_types": ["pocket", "holes"]
  },
  "suggestion_given": {
    "operation_type": "adaptive_clearing",
    "tool_diameter": 12.0,
    "stock_offset_xy": 5.0
  },
  "user_choice": {
    "accepted": false,
    "actual_operation": "pocket_clearing",
    "actual_tool_diameter": 10.0,
    "reason": "preferred_smaller_tool"
  }
}
```

**Output:**
```json
{
  "recorded": true,
  "feedback_id": 42,
  "preference_updated": "tool_selection",
  "new_confidence": 0.72
}
```

### 5.2 Feedback history table

```sql
CREATE TABLE IF NOT EXISTS cam_feedback_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Context
    geometry_hash TEXT,
    geometry_type TEXT,
    material TEXT,
    feature_types TEXT,  -- JSON array

    -- What we suggested
    suggestion_json TEXT,  -- Full suggestion as JSON

    -- What user chose
    user_choice_json TEXT,  -- Full choice as JSON
    accepted BOOLEAN,
    explicit_feedback TEXT,  -- Optional user comment

    -- Derived
    suggestion_type TEXT,  -- "stock", "strategy", "tool", "post"
    delta_json TEXT  -- Diff between suggestion and choice
);

CREATE INDEX IF NOT EXISTS idx_feedback_geometry
ON cam_feedback_history(geometry_hash);

CREATE INDEX IF NOT EXISTS idx_feedback_type
ON cam_feedback_history(suggestion_type, accepted);

CREATE INDEX IF NOT EXISTS idx_feedback_recent
ON cam_feedback_history(timestamp DESC);
```

### 5.3 Geometry hashing

```python
import hashlib
import json

def hash_geometry(geometry):
    """Create stable hash of geometry for similarity matching."""

    # Normalize and round values to avoid floating point issues
    normalized = {
        "bbox_x": round(geometry["bounding_box"]["x"], 0),
        "bbox_y": round(geometry["bounding_box"]["y"], 0),
        "bbox_z": round(geometry["bounding_box"]["z"], 0),
        "feature_types": sorted(set(f["type"] for f in geometry.get("features", []))),
        "min_radius": round(geometry.get("min_internal_radius", 0), 1)
    }

    # Create deterministic JSON string
    json_str = json.dumps(normalized, sort_keys=True)

    # Hash it
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]
```

### 5.4 Confidence update logic

```python
def update_preference_confidence(suggestion_type, context, accepted):
    """Update confidence score based on user feedback."""

    # Get current preference
    current = get_preference(suggestion_type, context)

    if current is None:
        # Create new preference from user's choice
        create_preference_from_choice(suggestion_type, context)
        return

    # Bayesian-ish update
    # If accepted: increase confidence
    # If rejected: decrease confidence, potentially update preferred value

    old_confidence = current["confidence"]
    usage_count = current["usage_count"]

    # Weight by usage count (more data = more stable)
    learning_rate = 1.0 / (usage_count + 5)  # Diminishes over time

    if accepted:
        new_confidence = old_confidence + learning_rate * (1.0 - old_confidence)
    else:
        new_confidence = old_confidence - learning_rate * old_confidence

    # Clamp to [0.1, 0.99]
    new_confidence = max(0.1, min(0.99, new_confidence))

    # Update in database
    update_preference(suggestion_type, context, {
        "confidence": new_confidence,
        "usage_count": usage_count + 1
    })

    return new_confidence
```

### 5.5 Preference update from rejection

```python
def handle_rejection(suggestion_type, context, suggestion, user_choice):
    """When user rejects, learn their actual preference."""

    if suggestion_type == "stock":
        # User preferred different offsets
        if user_choice.get("actual_offset_xy"):
            upsert_preference("cam_stock_preferences", {
                "geometry_type": context["geometry_type"],
                "material": context["material"],
                "preferred_offset_xy": user_choice["actual_offset_xy"],
                "confidence": 0.6,  # Start moderate
                "usage_count": 1
            })

    elif suggestion_type == "tool":
        # User preferred different tool
        if user_choice.get("actual_tool_diameter"):
            upsert_preference("cam_strategy_preferences", {
                "feature_type": context["feature_type"],
                "material": context["material"],
                "preferred_tool_diameter": user_choice["actual_tool_diameter"],
                "confidence": 0.6,
                "usage_count": 1
            })
```

### 5.6 Integrate learning into suggestions

```python
def suggest_with_learning(suggestion_type, context):
    """Make suggestion considering learned preferences."""

    # Get base suggestion from rules
    base_suggestion = get_rule_based_suggestion(suggestion_type, context)

    # Check for learned preference
    preference = get_preference(suggestion_type, context)

    if preference and preference["confidence"] > 0.7:
        # High confidence: use learned preference
        return {
            **preference["values"],
            "confidence": preference["confidence"],
            "from_preference": True,
            "source": f"learned from {preference['usage_count']} interactions"
        }

    elif preference and preference["confidence"] > 0.5:
        # Medium confidence: blend
        return blend_suggestions(base_suggestion, preference)

    else:
        # Low/no confidence: use rules
        return {
            **base_suggestion,
            "from_preference": False,
            "source": "rule-based default"
        }
```

### 5.7 Similarity-based suggestions

```python
def find_similar_feedback(geometry_hash, suggestion_type, limit=5):
    """Find feedback from similar geometries."""

    result = mcp.call('sqlite', {
        'input': {
            'sql': '''
                SELECT * FROM cam_feedback_history
                WHERE suggestion_type = ?
                  AND accepted = 1
                ORDER BY
                    CASE WHEN geometry_hash = ? THEN 0 ELSE 1 END,
                    timestamp DESC
                LIMIT ?
            ''',
            'params': [suggestion_type, geometry_hash, limit],
            'tool_unlock_token': '29e63eb5'
        }
    })

    return result.get('rows', [])
```

## Dependencies

- Phases 1-4 complete (all suggestion types working)
- SQLite accessible
- Geometry hashing working

## Notes

- Learning should be gradual — don't overfit to single choices
- Explicit feedback ("I prefer X because...") is gold
- Recency matters — recent choices may reflect new tools/materials

## Estimated Effort

- record_user_choice handler: 2 hours
- Feedback history table: 30 min
- Confidence update logic: 2 hours
- Preference from rejection: 1-2 hours
- Integration with suggestions: 2 hours
- Testing: 2 hours

---

*Phase 5 of Milestone 1: CAM Extension MVP*
