# Phase 3: Stock Suggestions

## Goal

Suggest stock setup based on geometry analysis and learned preferences.

## Success Criteria

- [ ] `suggest_stock_setup` returns ranked suggestions
- [ ] SQLite schema initialized for preferences
- [ ] Default offsets applied correctly
- [ ] Preferences influence suggestions

## Tasks

### 3.1 Implement suggest_stock_setup

**Input:**
```json
{
  "operation": "suggest_stock_setup",
  "body_names": ["Part1"],
  "stock_type": "rectangular",
  "consider_preferences": true
}
```

**Output:**
```json
{
  "suggestions": [
    {
      "rank": 1,
      "stock_type": "rectangular",
      "dimensions": {"x": 110, "y": 60, "z": 30},
      "offset": {"xy": 5.0, "z_top": 2.5, "z_bottom": 2.5},
      "orientation": "Z_UP",
      "confidence": 0.92,
      "reasoning": "Standard 5mm XY offset, minimal waste",
      "from_preference": true
    }
  ],
  "warnings": []
}
```

### 3.2 Stock calculation logic

```python
def calculate_stock_dimensions(bbox, offsets):
    return {
        "x": bbox["x"] + 2 * offsets["xy"],
        "y": bbox["y"] + 2 * offsets["xy"],
        "z": bbox["z"] + offsets["z_top"] + offsets["z_bottom"]
    }

# Default offsets by material
DEFAULT_OFFSETS = {
    "aluminum": {"xy": 5.0, "z_top": 2.5, "z_bottom": 2.5},
    "steel": {"xy": 3.0, "z_top": 2.0, "z_bottom": 2.0},
    "plastic": {"xy": 2.0, "z_top": 1.5, "z_bottom": 1.5},
    "default": {"xy": 5.0, "z_top": 2.5, "z_bottom": 2.5}
}
```

### 3.3 Initialize SQLite schema

Run via MCP sqlite tool:

```sql
-- Stock preferences table
CREATE TABLE IF NOT EXISTS cam_stock_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    geometry_type TEXT,
    material TEXT,
    preferred_offset_xy REAL,
    preferred_offset_z_top REAL,
    preferred_offset_z_bottom REAL,
    confidence REAL DEFAULT 0.5,
    usage_count INTEGER DEFAULT 0,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Machine profiles table
CREATE TABLE IF NOT EXISTS cam_machine_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    brand TEXT,
    model TEXT,
    controller TEXT,
    axes INTEGER,
    post_processor TEXT,
    max_spindle_speed INTEGER,
    max_feed_rate REAL,
    work_envelope_x REAL,
    work_envelope_y REAL,
    work_envelope_z REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookup
CREATE INDEX IF NOT EXISTS idx_stock_pref_lookup
ON cam_stock_preferences(geometry_type, material);
```

### 3.4 Preference lookup

```python
def get_stock_preferences(geometry_type, material):
    """Query stored preferences, return defaults if none found."""

    # Query via MCP sqlite tool
    result = mcp.call('sqlite', {
        'input': {
            'sql': '''
                SELECT * FROM cam_stock_preferences
                WHERE geometry_type = ? AND material = ?
                ORDER BY confidence DESC, usage_count DESC
                LIMIT 1
            ''',
            'params': [geometry_type, material],
            'tool_unlock_token': '29e63eb5'
        }
    })

    if result and result.get('rows'):
        row = result['rows'][0]
        return {
            "xy": row['preferred_offset_xy'],
            "z_top": row['preferred_offset_z_top'],
            "z_bottom": row['preferred_offset_z_bottom'],
            "confidence": row['confidence'],
            "from_preference": True
        }

    # Fall back to defaults
    return {
        **DEFAULT_OFFSETS.get(material, DEFAULT_OFFSETS["default"]),
        "confidence": 0.5,
        "from_preference": False
    }
```

### 3.5 Warning generation

```python
def generate_warnings(geometry, stock, tool_library):
    warnings = []

    # Check for deep features
    if geometry.get('max_depth', 0) > 50:
        warnings.append(f"Deep feature ({geometry['max_depth']}mm) - verify tool reach")

    # Check for small internal radii
    min_radius = geometry.get('min_internal_radius')
    if min_radius and min_radius < 1.5:
        warnings.append(f"Small internal radius ({min_radius}mm) - requires small tool")

    # Check stock fits machine
    # (would need machine profile)

    return warnings
```

## Dependencies

- Phase 2 complete (geometry analysis working)
- MCP sqlite tool accessible
- Test parts with known good stock setups

## Notes

- First suggestion should usually match user's intuition
- Confidence score helps AI explain suggestions
- Warnings should be actionable, not alarmist

## Estimated Effort

- suggest_stock_setup handler: 2 hours
- SQLite schema setup: 30 min
- Preference lookup: 1 hour
- Warning generation: 1 hour
- Testing: 1-2 hours

---

*Phase 3 of Milestone 1: CAM Extension MVP*
