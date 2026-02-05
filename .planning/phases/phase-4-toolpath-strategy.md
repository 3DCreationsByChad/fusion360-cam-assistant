# Phase 4: Toolpath Strategy Suggestions

## Goal

Recommend toolpath strategies based on geometry, material, and learned preferences.

## Success Criteria

- [ ] `suggest_toolpath_strategy` returns phased strategy
- [ ] Tool selection matches geometry constraints
- [ ] Feeds/speeds appropriate for material
- [ ] Strategy preferences table created and used

## Tasks

### 4.1 Implement suggest_toolpath_strategy

**Input:**
```json
{
  "operation": "suggest_toolpath_strategy",
  "body_names": ["Part1"],
  "machine_type": "3axis_vertical",
  "material": "aluminum_6061",
  "finish_quality": "standard",
  "consider_preferences": true
}
```

**Output:**
```json
{
  "strategy": {
    "phases": [
      {
        "name": "Roughing",
        "operation_type": "adaptive_clearing",
        "tool_suggestion": {
          "type": "flat_endmill",
          "diameter": 12.0,
          "flutes": 3
        },
        "parameters": {
          "stepdown": 4.0,
          "stepover_percent": 40,
          "feed_rate": 2000,
          "spindle_speed": 8000
        },
        "targets": ["full_part"],
        "confidence": 0.88
      }
    ],
    "total_estimated_time": "45 min"
  }
}
```

### 4.2 Feature-to-operation mapping

```python
FEATURE_OPERATION_MAP = {
    "pocket": {
        "roughing": ["adaptive_clearing", "pocket_clearing"],
        "finishing": ["contour", "parallel"]
    },
    "hole": {
        "operations": ["drill", "bore", "ream"]
    },
    "slot": {
        "roughing": ["slot_clearing"],
        "finishing": ["contour"]
    },
    "contour": {
        "operations": ["2d_contour", "trace"]
    },
    "face": {
        "operations": ["face", "parallel"]
    }
}

def get_operations_for_features(features):
    """Map detected features to required operations."""
    operations = []

    for feature in features:
        feature_type = feature["type"]
        if feature_type in FEATURE_OPERATION_MAP:
            ops = FEATURE_OPERATION_MAP[feature_type]
            operations.extend(ops.get("roughing", []))
            operations.extend(ops.get("finishing", []))
            operations.extend(ops.get("operations", []))

    return list(set(operations))  # deduplicate
```

### 4.3 Tool selection logic

```python
def select_tool_for_operation(operation_type, geometry, tool_library):
    """Select best tool from library for operation."""

    min_radius = geometry.get("min_internal_radius", float("inf"))
    max_depth = geometry.get("max_depth", 0)

    # Filter compatible tools
    candidates = []
    for tool in tool_library:
        # Tool must fit smallest feature
        if tool["diameter"] / 2 <= min_radius:
            # Tool must reach deepest feature
            if tool.get("flute_length", 100) >= max_depth:
                candidates.append(tool)

    if not candidates:
        return None

    # Prefer largest compatible tool (more rigid, faster)
    candidates.sort(key=lambda t: t["diameter"], reverse=True)
    return candidates[0]
```

### 4.4 Feeds and speeds calculation

```python
# Material cutting data (SFM = Surface Feet per Minute)
MATERIAL_DATA = {
    "aluminum_6061": {
        "sfm_roughing": 800,
        "sfm_finishing": 1000,
        "chip_load_per_flute": 0.004,  # inches
        "max_doc": 0.5  # depth of cut as fraction of diameter
    },
    "steel_1018": {
        "sfm_roughing": 300,
        "sfm_finishing": 400,
        "chip_load_per_flute": 0.003,
        "max_doc": 0.3
    },
    "plastic_abs": {
        "sfm_roughing": 500,
        "sfm_finishing": 600,
        "chip_load_per_flute": 0.006,
        "max_doc": 0.75
    }
}

def calculate_feeds_speeds(tool, material, operation_type):
    """Calculate feeds and speeds for tool/material combo."""

    mat_data = MATERIAL_DATA.get(material, MATERIAL_DATA["aluminum_6061"])

    if "rough" in operation_type.lower():
        sfm = mat_data["sfm_roughing"]
    else:
        sfm = mat_data["sfm_finishing"]

    # RPM = (SFM * 12) / (π * diameter_inches)
    diameter_inches = tool["diameter"] / 25.4
    rpm = int((sfm * 12) / (3.14159 * diameter_inches))

    # Feed = RPM * flutes * chip_load
    flutes = tool.get("flutes", 2)
    chip_load = mat_data["chip_load_per_flute"]
    feed_ipm = rpm * flutes * chip_load
    feed_mmpm = int(feed_ipm * 25.4)

    # Depth of cut
    doc = tool["diameter"] * mat_data["max_doc"]

    return {
        "spindle_speed": rpm,
        "feed_rate": feed_mmpm,
        "stepdown": round(doc, 1),
        "stepover_percent": 40 if "rough" in operation_type.lower() else 15
    }
```

### 4.5 Strategy preferences table

```sql
CREATE TABLE IF NOT EXISTS cam_strategy_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_type TEXT,
    material TEXT,
    machine_type TEXT,
    preferred_operation TEXT,
    preferred_tool_type TEXT,
    preferred_tool_diameter REAL,
    confidence REAL DEFAULT 0.5,
    usage_count INTEGER DEFAULT 0,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_strategy_lookup
ON cam_strategy_preferences(feature_type, material, machine_type);
```

### 4.6 Build strategy phases

```python
def build_strategy(geometry, material, machine_type, tool_library, preferences):
    """Build complete machining strategy."""

    phases = []

    # Phase 1: Roughing (always first)
    rough_tool = select_tool_for_operation("roughing", geometry, tool_library)
    if rough_tool:
        phases.append({
            "name": "Roughing",
            "operation_type": "adaptive_clearing",
            "tool_suggestion": rough_tool,
            "parameters": calculate_feeds_speeds(rough_tool, material, "roughing"),
            "targets": ["full_part"],
            "confidence": 0.85
        })

    # Phase 2: Feature-specific operations
    for feature in geometry.get("features", []):
        if feature["type"] == "pocket":
            # Add pocket clearing
            pass
        elif feature["type"] == "hole":
            # Add drilling
            pass

    # Phase 3: Finishing
    finish_tool = select_tool_for_operation("finishing", geometry, tool_library)
    if finish_tool:
        phases.append({
            "name": "Finishing",
            "operation_type": "contour",
            "tool_suggestion": finish_tool,
            "parameters": calculate_feeds_speeds(finish_tool, material, "finishing"),
            "targets": ["walls", "floors"],
            "confidence": 0.80
        })

    return {"phases": phases}
```

## Dependencies

- Phase 2 complete (geometry analysis)
- Phase 3 complete (stock setup)
- Tool library queryable

## Notes

- Feeds/speeds are starting points — user should verify
- Strategy should be conservative (can always go faster)
- Preferences override defaults when confidence is high

## Estimated Effort

- suggest_toolpath_strategy handler: 3-4 hours
- Feature-to-operation mapping: 1-2 hours
- Tool selection: 1-2 hours
- Feeds/speeds calculation: 2 hours
- Testing: 2 hours

---

*Phase 4 of Milestone 1: CAM Extension MVP*
