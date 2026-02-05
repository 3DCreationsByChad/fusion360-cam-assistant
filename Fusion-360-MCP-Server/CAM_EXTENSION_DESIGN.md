# CAM Extension Design for Fusion 360 MCP Server

## Overview

Extend the existing MCP server to support AI-assisted CAM workflows:
- Analyze geometry for manufacturability
- Suggest stock setup and orientation
- Recommend toolpath strategies
- Learn from user preferences and feedback

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI Assistant                              │
│  (Claude/Local LLM via MCP)                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MCP-Link Server                              │
│  - Routes tool calls                                            │
│  - SQLite for preference storage                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Fusion 360 MCP Add-in (Extended)                   │
├─────────────────────────────────────────────────────────────────┤
│  EXISTING                  │  NEW CAM EXTENSION                 │
│  ─────────────────────────│──────────────────────────────────  │
│  • Generic API calls       │  • analyze_geometry_for_cam        │
│  • Python execution        │  • suggest_stock_setup             │
│  • Script management       │  • suggest_toolpath_strategy       │
│  • API documentation       │  • get_cam_state                   │
│                            │  • record_user_choice              │
│                            │  • get_tool_library                │
│                            │  • suggest_post_processor          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Fusion 360 CAM API                           │
│  adsk.cam module - Setups, Operations, Tools, Posts             │
└─────────────────────────────────────────────────────────────────┘
```

---

## New CAM Operations

### 1. `analyze_geometry_for_cam`

Analyzes the current design and returns CAM-relevant information.

**Input:**
```json
{
  "operation": "analyze_geometry_for_cam",
  "body_names": ["Part1"],           // Optional: specific bodies
  "analysis_type": "full"            // "full", "quick", "features_only"
}
```

**Output:**
```json
{
  "bounding_box": {
    "x": 100.0, "y": 50.0, "z": 25.0,
    "unit": "mm"
  },
  "volume": 125000.0,
  "surface_area": 17500.0,
  "features": [
    {"type": "pocket", "depth": 10.0, "area": 500.0, "corners": "sharp"},
    {"type": "hole", "diameter": 6.0, "depth": 15.0, "count": 4},
    {"type": "slot", "width": 8.0, "length": 40.0, "depth": 5.0}
  ],
  "min_internal_radius": 3.0,
  "max_depth": 15.0,
  "undercuts": false,
  "suggested_orientations": [
    {"axis": "Z_UP", "score": 0.9, "reason": "Most features accessible from top"},
    {"axis": "Y_UP", "score": 0.6, "reason": "Side features accessible"}
  ],
  "material_hints": {
    "from_appearance": "Aluminum",
    "from_material": "6061-T6"
  }
}
```

**Implementation Location:** `mcp_integration.py` line ~430

```python
elif operation == 'analyze_geometry_for_cam':
    return _handle_analyze_geometry_for_cam(arguments)
```

---

### 2. `suggest_stock_setup`

Suggests stock dimensions and orientation based on geometry and preferences.

**Input:**
```json
{
  "operation": "suggest_stock_setup",
  "body_names": ["Part1"],
  "stock_type": "rectangular",       // "rectangular", "cylindrical", "from_body"
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
      "dimensions": {"x": 110.0, "y": 60.0, "z": 30.0},
      "offset": {"xy": 5.0, "z_top": 2.5, "z_bottom": 2.5},
      "orientation": "Z_UP",
      "confidence": 0.92,
      "reasoning": "Standard 5mm XY offset, minimal material waste",
      "from_preference": true,
      "preference_source": "user_history_2024-01"
    },
    {
      "rank": 2,
      "stock_type": "rectangular",
      "dimensions": {"x": 105.0, "y": 55.0, "z": 28.0},
      "offset": {"xy": 2.5, "z_top": 1.5, "z_bottom": 1.5},
      "orientation": "Z_UP",
      "confidence": 0.78,
      "reasoning": "Tighter tolerances, less material waste"
    }
  ],
  "warnings": [
    "Part has deep pocket (15mm) - ensure adequate tool reach"
  ]
}
```

---

### 3. `suggest_toolpath_strategy`

Recommends toolpath strategies based on geometry and machining context.

**Input:**
```json
{
  "operation": "suggest_toolpath_strategy",
  "body_names": ["Part1"],
  "machine_type": "3axis_vertical",  // "3axis_vertical", "3axis_horizontal", "4axis", "5axis"
  "material": "aluminum_6061",
  "finish_quality": "standard",       // "rough", "standard", "fine"
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
          "flutes": 3,
          "material": "carbide"
        },
        "parameters": {
          "stepdown": 4.0,
          "stepover_percent": 40,
          "feed_rate": 2000,
          "spindle_speed": 8000,
          "coolant": "flood"
        },
        "targets": ["full_part"],
        "confidence": 0.88,
        "reasoning": "Adaptive clearing efficient for aluminum, 3-flute for chip evacuation"
      },
      {
        "name": "Pockets",
        "operation_type": "pocket_clearing",
        "tool_suggestion": {
          "type": "flat_endmill",
          "diameter": 6.0,
          "flutes": 2,
          "corner_radius": 0.0
        },
        "parameters": {
          "stepdown": 2.0,
          "stepover_percent": 50,
          "feed_rate": 1500,
          "spindle_speed": 10000
        },
        "targets": ["pocket_1", "pocket_2"],
        "confidence": 0.85
      },
      {
        "name": "Finishing",
        "operation_type": "contour",
        "tool_suggestion": {
          "type": "ball_endmill",
          "diameter": 6.0
        },
        "parameters": {
          "stepover": 0.5,
          "feed_rate": 1000,
          "spindle_speed": 12000
        },
        "targets": ["walls", "floors"],
        "confidence": 0.82
      },
      {
        "name": "Holes",
        "operation_type": "drill",
        "tool_suggestion": {
          "type": "drill",
          "diameter": 5.0
        },
        "parameters": {
          "peck_depth": 3.0,
          "feed_rate": 200,
          "spindle_speed": 3000
        },
        "targets": ["hole_pattern_1"],
        "confidence": 0.95
      }
    ],
    "total_estimated_time": "45 min",
    "from_preferences": {
      "adaptive_clearing": "user preferred over pocket for roughing",
      "tool_selection": "matches user's tool library"
    }
  },
  "alternatives": [
    {
      "name": "Conservative Strategy",
      "difference": "Smaller tools, lighter cuts",
      "time_estimate": "65 min",
      "when_to_use": "Thin walls, delicate features"
    }
  ]
}
```

---

### 4. `get_cam_state`

Returns current CAM setup state for context awareness.

**Input:**
```json
{
  "operation": "get_cam_state"
}
```

**Output:**
```json
{
  "has_cam_workspace": true,
  "setups": [
    {
      "name": "Setup1",
      "stock": {
        "type": "rectangular",
        "dimensions": {"x": 110, "y": 60, "z": 30}
      },
      "wcs": "top_center",
      "operations": [
        {"name": "Adaptive1", "type": "adaptive", "status": "valid"},
        {"name": "Contour1", "type": "contour", "status": "needs_regenerate"}
      ]
    }
  ],
  "active_setup": "Setup1",
  "post_processor": "fanuc.cps",
  "machine": {
    "name": "Generic 3-Axis",
    "type": "mill",
    "axes": 3
  }
}
```

---

### 5. `record_user_choice`

Records user's actual choice for preference learning.

**Input:**
```json
{
  "operation": "record_user_choice",
  "context": {
    "geometry_hash": "abc123",
    "material": "aluminum_6061",
    "feature_types": ["pocket", "holes"]
  },
  "suggestion_given": {
    "operation_type": "adaptive_clearing",
    "tool_diameter": 12.0
  },
  "user_choice": {
    "accepted": false,
    "actual_operation": "pocket_clearing",
    "actual_tool_diameter": 10.0,
    "reason": "preferred_smaller_tool"  // Optional user feedback
  }
}
```

**Output:**
```json
{
  "recorded": true,
  "preference_updated": "tool_selection",
  "new_confidence": 0.75
}
```

---

### 6. `get_tool_library`

Returns available tools from Fusion's tool library.

**Input:**
```json
{
  "operation": "get_tool_library",
  "filter": {
    "type": ["endmill", "drill"],
    "diameter_range": [3.0, 20.0],
    "material": "carbide"
  }
}
```

**Output:**
```json
{
  "tools": [
    {
      "id": "tool_1",
      "description": "12mm 3-Flute Carbide Endmill",
      "type": "flat_endmill",
      "diameter": 12.0,
      "flutes": 3,
      "flute_length": 30.0,
      "overall_length": 75.0,
      "material": "carbide",
      "coating": "TiAlN",
      "vendor": "Harvey Tool",
      "part_number": "HT-12345"
    }
  ],
  "total_count": 47
}
```

---

### 7. `suggest_post_processor`

Suggests post-processor based on machine profile.

**Input:**
```json
{
  "operation": "suggest_post_processor",
  "machine_brand": "Haas",
  "machine_model": "VF-2",
  "controller": "NGC"
}
```

**Output:**
```json
{
  "suggestions": [
    {
      "name": "haas.cps",
      "path": "C:/Users/.../Posts/haas.cps",
      "confidence": 0.95,
      "features": ["rigid_tapping", "high_speed_mode"]
    }
  ],
  "from_preference": true
}
```

---

## Data Storage Schema (SQLite via MCP)

### Tables

```sql
-- User preferences for stock setup
CREATE TABLE cam_stock_preferences (
    id INTEGER PRIMARY KEY,
    geometry_type TEXT,           -- "prismatic", "rotational", "complex"
    material TEXT,
    preferred_offset_xy REAL,
    preferred_offset_z_top REAL,
    preferred_offset_z_bottom REAL,
    confidence REAL,
    usage_count INTEGER,
    last_used TIMESTAMP
);

-- User preferences for toolpath strategies
CREATE TABLE cam_strategy_preferences (
    id INTEGER PRIMARY KEY,
    feature_type TEXT,            -- "pocket", "hole", "contour", "face"
    material TEXT,
    machine_type TEXT,
    preferred_operation TEXT,     -- "adaptive", "pocket", "parallel", etc.
    preferred_tool_type TEXT,
    preferred_tool_diameter REAL,
    confidence REAL,
    usage_count INTEGER,
    last_used TIMESTAMP
);

-- Feedback history for learning
CREATE TABLE cam_feedback_history (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP,
    geometry_hash TEXT,
    suggestion_json TEXT,
    user_choice_json TEXT,
    accepted BOOLEAN,
    explicit_feedback TEXT
);

-- Machine profiles
CREATE TABLE cam_machine_profiles (
    id INTEGER PRIMARY KEY,
    name TEXT,
    brand TEXT,
    model TEXT,
    controller TEXT,
    axes INTEGER,
    post_processor TEXT,
    max_spindle_speed INTEGER,
    max_feed_rate REAL,
    work_envelope_json TEXT
);
```

---

## Implementation Plan

### Phase 1: Foundation (Core CAM Access)
1. Add `get_cam_state` operation
2. Add `get_tool_library` operation
3. Add `analyze_geometry_for_cam` operation
4. Create SQLite schema

### Phase 2: Suggestions (Intelligence Layer)
5. Add `suggest_stock_setup` operation
6. Add `suggest_toolpath_strategy` operation
7. Add `suggest_post_processor` operation
8. Implement basic heuristics for suggestions

### Phase 3: Learning (Preference System)
9. Add `record_user_choice` operation
10. Implement preference storage
11. Add preference weighting to suggestions
12. Build confidence scoring

### Phase 4: Integration (AI Assistant)
13. Create CAM-specific prompts for AI
14. Build conversation flow for CAM workflow
15. Add real-time observation hooks (optional)
16. Testing and refinement

---

## Code Snippets

### Adding CAM Operations to mcp_integration.py

```python
# Add after line 432 in mcp_integration.py

elif operation == 'analyze_geometry_for_cam':
    return _handle_analyze_geometry_for_cam(arguments)
elif operation == 'suggest_stock_setup':
    return _handle_suggest_stock_setup(arguments)
elif operation == 'suggest_toolpath_strategy':
    return _handle_suggest_toolpath_strategy(arguments)
elif operation == 'get_cam_state':
    return _handle_get_cam_state(arguments)
elif operation == 'record_user_choice':
    return _handle_record_user_choice(arguments)
elif operation == 'get_tool_library':
    return _handle_get_tool_library(arguments)
elif operation == 'suggest_post_processor':
    return _handle_suggest_post_processor(arguments)
```

### Sample Handler: get_cam_state

```python
def _handle_get_cam_state(arguments: dict) -> dict:
    """Get current CAM workspace state."""
    try:
        import adsk.core
        import adsk.fusion
        import adsk.cam

        app = adsk.core.Application.get()

        # Check if CAM workspace is available
        cam_product = None
        for product in app.activeDocument.products:
            if isinstance(product, adsk.cam.CAM):
                cam_product = product
                break

        if not cam_product:
            return {
                "content": [{"type": "text", "text": json.dumps({
                    "has_cam_workspace": False,
                    "message": "No CAM workspace in current document"
                }, indent=2)}],
                "isError": False
            }

        # Gather setup information
        setups_data = []
        for setup in cam_product.setups:
            setup_info = {
                "name": setup.name,
                "operations": []
            }

            # Get stock info
            stock_mode = setup.stockMode
            if stock_mode == adsk.cam.StockModes.FixedBoxStock:
                setup_info["stock"] = {
                    "type": "rectangular",
                    "dimensions": {
                        "x": setup.stockXLength,
                        "y": setup.stockYLength,
                        "z": setup.stockZLength
                    }
                }

            # Get operations
            for op in setup.operations:
                setup_info["operations"].append({
                    "name": op.name,
                    "type": op.objectType.split("::")[-1],
                    "status": "valid" if op.isValid else "invalid"
                })

            setups_data.append(setup_info)

        result = {
            "has_cam_workspace": True,
            "setups": setups_data,
            "active_setup": cam_product.activeSetup.name if cam_product.activeSetup else None
        }

        return {
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
            "isError": False
        }

    except Exception as e:
        import traceback
        return {
            "content": [{"type": "text", "text": f"ERROR: {str(e)}\n{traceback.format_exc()}"}],
            "isError": True
        }
```

### Sample Handler: analyze_geometry_for_cam

```python
def _handle_analyze_geometry_for_cam(arguments: dict) -> dict:
    """Analyze geometry for CAM manufacturability."""
    try:
        import adsk.core
        import adsk.fusion

        app = adsk.core.Application.get()
        design = adsk.fusion.Design.cast(app.activeProduct)
        rootComp = design.rootComponent

        body_names = arguments.get('body_names', [])
        analysis_type = arguments.get('analysis_type', 'full')

        # Get bodies to analyze
        bodies = []
        if body_names:
            for body in rootComp.bRepBodies:
                if body.name in body_names:
                    bodies.append(body)
        else:
            bodies = list(rootComp.bRepBodies)

        if not bodies:
            return {
                "content": [{"type": "text", "text": "No bodies found to analyze"}],
                "isError": True
            }

        results = []
        for body in bodies:
            bbox = body.boundingBox

            body_result = {
                "name": body.name,
                "bounding_box": {
                    "x": (bbox.maxPoint.x - bbox.minPoint.x) * 10,  # cm to mm
                    "y": (bbox.maxPoint.y - bbox.minPoint.y) * 10,
                    "z": (bbox.maxPoint.z - bbox.minPoint.z) * 10,
                    "unit": "mm"
                },
                "volume": body.volume * 1000,  # cm³ to mm³
                "surface_area": body.surfaceArea * 100,  # cm² to mm²
            }

            if analysis_type in ['full', 'features_only']:
                # Analyze faces for feature detection
                features = []
                min_radius = float('inf')

                for face in body.faces:
                    geom = face.geometry

                    # Detect cylindrical features (holes, bosses)
                    if isinstance(geom, adsk.core.Cylinder):
                        radius = geom.radius * 10  # to mm
                        if radius < min_radius:
                            min_radius = radius
                        features.append({
                            "type": "cylindrical",
                            "radius": radius
                        })

                    # Detect planar faces (potential pocket floors)
                    elif isinstance(geom, adsk.core.Plane):
                        area = face.area * 100  # to mm²
                        if area > 10:  # Ignore tiny faces
                            features.append({
                                "type": "planar",
                                "area": area
                            })

                body_result["feature_count"] = len(features)
                body_result["min_internal_radius"] = min_radius if min_radius != float('inf') else None

            # Suggest orientations based on bounding box
            dims = body_result["bounding_box"]
            orientations = []

            # Prefer orientation with largest face down (most stable)
            if dims["x"] * dims["y"] >= dims["x"] * dims["z"] and dims["x"] * dims["y"] >= dims["y"] * dims["z"]:
                orientations.append({"axis": "Z_UP", "score": 0.9, "reason": "Largest face as base"})
            if dims["x"] * dims["z"] >= dims["x"] * dims["y"]:
                orientations.append({"axis": "Y_UP", "score": 0.7, "reason": "Good for side features"})

            body_result["suggested_orientations"] = orientations
            results.append(body_result)

        return {
            "content": [{"type": "text", "text": json.dumps({
                "bodies_analyzed": len(results),
                "results": results
            }, indent=2)}],
            "isError": False
        }

    except Exception as e:
        import traceback
        return {
            "content": [{"type": "text", "text": f"ERROR: {str(e)}\n{traceback.format_exc()}"}],
            "isError": True
        }
```

---

## CAM Best Practices (Add to best_practices.md)

```markdown
## CAM-Specific Best Practices

### Stock Setup
- **Default offsets**: 5mm XY, 2.5mm Z for aluminum
- **Orientation**: Prefer Z-up for 3-axis, most features accessible from top
- **Stock type**: Rectangular for prismatic parts, cylindrical for turned parts

### Toolpath Strategy
- **Roughing first**: Always rough before finishing
- **Adaptive clearing**: Preferred for aluminum, good chip evacuation
- **Tool selection**: Largest tool that fits the smallest feature
- **Stepover**: 40% for roughing, 10-15% for finishing

### Tool Selection Rules
- **Minimum tool diameter**: 2x smallest internal radius
- **Flute count**: 2-3 for aluminum, 4+ for steel
- **Stick-out**: Minimize for rigidity, must clear deepest feature

### Feeds and Speeds (Aluminum 6061)
- **Roughing**: 0.1mm/tooth, 200-300 SFM
- **Finishing**: 0.05mm/tooth, 300-400 SFM
- **Drilling**: 0.05mm/rev for standard drills
```

---

## Next Steps

1. **Create `cam_operations.py`** - New module for CAM handlers (keeps mcp_integration.py cleaner)
2. **Initialize SQLite schema** - Run setup script via MCP sqlite tool
3. **Implement Phase 1 handlers** - get_cam_state, get_tool_library, analyze_geometry
4. **Test with real parts** - Validate analysis accuracy
5. **Iterate on suggestion logic** - Refine heuristics based on testing

---

*This design aligns with PROJECT.md requirements:*
- *Overlay integrates with Fusion 360 UI* → MCP provides the integration layer
- *Detects part geometry* → `analyze_geometry_for_cam`
- *Suggests stock orientation* → `suggest_stock_setup`
- *Recommends toolpath strategy* → `suggest_toolpath_strategy`
- *Maintains preference memory* → SQLite storage + `record_user_choice`
