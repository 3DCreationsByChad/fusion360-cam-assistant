# Phase 6: Post-Processor & Polish

## Goal

Complete the CAM suggestion loop with post-processor recommendations and polish the extension for release.

## Success Criteria

- [ ] `suggest_post_processor` matches machine to post
- [ ] CAM best practices documented
- [ ] End-to-end workflow tested
- [ ] README updated with CAM features

## Tasks

### 6.1 Implement suggest_post_processor

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
      "features": ["rigid_tapping", "high_speed_mode"],
      "from_preference": true
    }
  ],
  "fallback": "generic-3axis.cps"
}
```

### 6.2 Post-processor matching

```python
# Common post-processor mappings
POST_MAPPINGS = {
    "haas": {
        "default": "haas.cps",
        "models": {
            "VF": "haas.cps",
            "TM": "haas-turning.cps",
            "UMC": "haas-5axis.cps"
        }
    },
    "fanuc": {
        "default": "fanuc.cps",
        "controllers": {
            "0i": "fanuc.cps",
            "30i": "fanuc.cps",
            "31i": "fanuc.cps"
        }
    },
    "mazak": {
        "default": "mazak.cps"
    },
    "okuma": {
        "default": "okuma.cps"
    },
    "dmg_mori": {
        "default": "dmg-mori.cps"
    }
}

def suggest_post(brand, model=None, controller=None):
    """Suggest post-processor for machine."""

    brand_lower = brand.lower().replace(" ", "_")

    if brand_lower not in POST_MAPPINGS:
        return {"name": "generic-3axis.cps", "confidence": 0.3}

    mapping = POST_MAPPINGS[brand_lower]

    # Try specific model match
    if model and "models" in mapping:
        for prefix, post in mapping["models"].items():
            if model.upper().startswith(prefix):
                return {"name": post, "confidence": 0.9}

    # Try controller match
    if controller and "controllers" in mapping:
        if controller in mapping["controllers"]:
            return {"name": mapping["controllers"][controller], "confidence": 0.85}

    # Fall back to brand default
    return {"name": mapping["default"], "confidence": 0.7}
```

### 6.3 Query machine profile from preferences

```python
def get_or_create_machine_profile(name):
    """Get machine profile from database, or create stub."""

    result = mcp.call('sqlite', {
        'input': {
            'sql': 'SELECT * FROM cam_machine_profiles WHERE name = ?',
            'params': [name],
            'tool_unlock_token': '29e63eb5'
        }
    })

    if result.get('rows'):
        return result['rows'][0]

    # Return stub for new machine
    return {
        "name": name,
        "brand": None,
        "model": None,
        "controller": None,
        "post_processor": None,
        "is_new": True
    }
```

### 6.4 Add CAM best practices to best_practices.md

Add section to `Fusion-360-MCP-Server/best_practices.md`:

```markdown
## CAM-Specific Best Practices

### Stock Setup
- **Default offsets**: 5mm XY, 2.5mm Z for aluminum
- **Orientation**: Prefer Z-up for 3-axis, most features accessible from top
- **Stock type**: Rectangular for prismatic, cylindrical for turned parts

### Toolpath Strategy Order
1. **Face** the top surface first (establishes Z datum)
2. **Rough** with largest appropriate tool
3. **Semi-finish** for tight corners
4. **Finish** walls and floors
5. **Drill** holes last (avoids chip accumulation)

### Tool Selection Rules
- **Minimum diameter**: 2x smallest internal radius
- **Flute count**: 2-3 for aluminum, 4+ for steel
- **Stick-out**: Minimize for rigidity
- **Corner radius**: Match fillet radii where possible

### Feeds and Speeds Guidelines

| Material | SFM Rough | SFM Finish | Chip Load |
|----------|-----------|------------|-----------|
| Aluminum 6061 | 800 | 1000 | 0.004"/tooth |
| Steel 1018 | 300 | 400 | 0.003"/tooth |
| Stainless 304 | 150 | 200 | 0.002"/tooth |
| Plastic ABS | 500 | 600 | 0.006"/tooth |

### Common Pitfalls
- ❌ Tool too small for roughing (slow, poor finish)
- ❌ Too aggressive stepdown (chatter, tool breakage)
- ❌ Ignoring chip evacuation (recutting chips)
- ❌ Wrong post-processor (crashes, incorrect code)
```

### 6.5 End-to-end testing

Test scenarios:

1. **Simple prismatic part**
   - Rectangular with pockets and holes
   - Verify: geometry analysis, stock setup, toolpath strategy

2. **Complex multi-feature part**
   - Multiple pockets, slots, contours
   - Verify: correct operation ordering, tool selection

3. **Learning loop**
   - Make suggestion, record rejection
   - Make another suggestion, verify preference applied

4. **Post-processor flow**
   - Set machine profile
   - Verify post suggestion

### 6.6 Update documentation

**README.md additions:**

```markdown
## CAM Workflow Assistance

The Fusion 360 MCP Server includes CAM-specific operations:

### Available Operations

| Operation | Description |
|-----------|-------------|
| `get_cam_state` | Query current CAM setup state |
| `get_tool_library` | Search available cutting tools |
| `analyze_geometry_for_cam` | Analyze part for manufacturability |
| `suggest_stock_setup` | Recommend stock dimensions and orientation |
| `suggest_toolpath_strategy` | Recommend machining strategy |
| `record_user_choice` | Store feedback for learning |
| `suggest_post_processor` | Match machine to post-processor |

### Example: Get CAM Suggestions

```json
{
  "operation": "suggest_toolpath_strategy",
  "body_names": ["Part1"],
  "machine_type": "3axis_vertical",
  "material": "aluminum_6061"
}
```

### Learning System

The assistant learns from your choices. When you accept or modify a suggestion, use `record_user_choice` to improve future recommendations.
```

### 6.7 Release checklist

- [ ] All handlers return proper MCP response format
- [ ] Error handling doesn't crash add-in
- [ ] SQLite tables created on first use
- [ ] Logging helpful for debugging
- [ ] README documents all CAM operations
- [ ] best_practices.md includes CAM section
- [ ] Tested with Fusion 360 2024+

## Dependencies

- Phases 1-5 complete
- Test parts available
- Documentation reviewed

## Notes

- Keep README focused on usage, not internals
- Best practices should match industry standards
- Testing with real workflow is critical

## Estimated Effort

- suggest_post_processor: 1-2 hours
- Best practices documentation: 1 hour
- End-to-end testing: 2-3 hours
- README/documentation: 1-2 hours
- Bug fixes from testing: 2-4 hours

---

*Phase 6 of Milestone 1: CAM Extension MVP*

---

## Milestone 1 Complete

After Phase 6, the CAM Extension MVP is complete:

- ✅ Query CAM state from Fusion 360
- ✅ Analyze geometry for manufacturability
- ✅ Suggest stock setup with preferences
- ✅ Recommend toolpath strategies
- ✅ Learn from user feedback
- ✅ Suggest post-processors
- ✅ Documentation complete

**Next:** Milestone 2 — Real-Time Observation (optional)
