# Fusion 360 AI CAM Assistant — Roadmap

## Milestone 1: CAM Extension MVP

**Goal:** Extend Fusion-360-MCP-Server with core CAM operations that analyze geometry and provide basic suggestions.

**Success Criteria:**
- Can query current CAM state from Fusion 360
- Can analyze geometry and return CAM-relevant features
- Can suggest stock setup based on bounding box
- Can query tool library
- Preferences stored in SQLite

---

## Phase 1: Foundation — CAM State Access

**Goal:** Establish basic CAM API access and state querying.

### Tasks

1. **Create `cam_operations.py` module**
   - New file for CAM-specific handlers
   - Import into `mcp_integration.py`
   - Keep main file clean

2. **Implement `get_cam_state` operation**
   - Check if CAM workspace exists
   - List all setups with stock info
   - List operations per setup
   - Return machine/post-processor info

3. **Implement `get_tool_library` operation**
   - Query Fusion's tool library
   - Filter by type, diameter, material
   - Return tool specifications

4. **Test with Fusion 360**
   - Load add-in manually
   - Verify operations work via MCP
   - Document any API quirks

### Deliverables
- `cam_operations.py` with `get_cam_state`, `get_tool_library`
- Updated `mcp_integration.py` routing
- Test results documented

---

## Phase 2: Geometry Analysis

**Goal:** Analyze part geometry to extract CAM-relevant information.

### Tasks

1. **Implement `analyze_geometry_for_cam` operation**
   - Calculate bounding box (with units)
   - Compute volume and surface area
   - Detect feature types (cylindrical, planar faces)
   - Find minimum internal radius
   - Suggest orientations based on geometry

2. **Feature detection heuristics**
   - Identify pockets (enclosed planar regions)
   - Identify holes (cylindrical features)
   - Identify slots (elongated pockets)
   - Calculate max depth

3. **Material detection**
   - Read material from body properties
   - Read appearance for hints
   - Default to "unknown" if not set

### Deliverables
- `analyze_geometry_for_cam` handler
- Feature detection working for common geometries
- Sample output for test parts

---

## Phase 3: Stock Suggestions

**Goal:** Suggest stock setup based on geometry analysis.

### Tasks

1. **Implement `suggest_stock_setup` operation**
   - Calculate stock dimensions from bounding box
   - Apply default offsets (5mm XY, 2.5mm Z)
   - Suggest orientation based on feature accessibility
   - Provide confidence score and reasoning

2. **Initialize SQLite schema**
   - Create `cam_stock_preferences` table
   - Create `cam_machine_profiles` table
   - Run via MCP sqlite tool

3. **Basic preference lookup**
   - Query preferences by geometry type
   - Merge with defaults
   - Return source of suggestion

### Deliverables
- `suggest_stock_setup` handler
- SQLite schema initialized
- Preferences influencing suggestions

---

## Phase 4: Toolpath Strategy Suggestions

**Goal:** Recommend toolpath strategies based on geometry and material.

### Tasks

1. **Implement `suggest_toolpath_strategy` operation**
   - Analyze features to determine required operations
   - Suggest roughing strategy (adaptive vs pocket)
   - Suggest finishing strategy
   - Recommend tools from library
   - Calculate basic feeds/speeds

2. **Strategy rules engine**
   - Map feature types to operation types
   - Material-based parameter adjustments
   - Tool selection logic (largest that fits)

3. **Create `cam_strategy_preferences` table**
   - Store preferred operations per feature type
   - Store preferred tool selections
   - Track confidence scores

### Deliverables
- `suggest_toolpath_strategy` handler
- Rules engine for common scenarios
- Strategy preferences table

---

## Phase 5: Learning System

**Goal:** Learn from user choices to improve future suggestions.

### Tasks

1. **Implement `record_user_choice` operation**
   - Store suggestion given
   - Store user's actual choice
   - Track acceptance rate
   - Optional explicit feedback

2. **Create `cam_feedback_history` table**
   - Full history of suggestions
   - Geometry hash for similarity matching
   - Timestamps for recency weighting

3. **Preference update logic**
   - Update confidence scores based on feedback
   - Weight recent choices higher
   - Decay old preferences

4. **Integrate learning into suggestions**
   - Query feedback history for similar geometries
   - Adjust suggestions based on past choices
   - Show "from preference" source

### Deliverables
- `record_user_choice` handler
- Feedback history table
- Learning influencing suggestions

---

## Phase 6: Post-Processor & Polish

**Goal:** Complete the suggestion loop with post-processor recommendations.

### Tasks

1. **Implement `suggest_post_processor` operation**
   - Match machine profile to post
   - Query from preferences
   - Fallback to generic

2. **Add CAM best practices to documentation**
   - Update `best_practices.md`
   - Document CAM-specific guidelines
   - Add example workflows

3. **End-to-end testing**
   - Test full workflow with real parts
   - Validate suggestions are sensible
   - Fix edge cases

4. **Documentation**
   - Update README with CAM features
   - Document new operations
   - Usage examples

### Deliverables
- `suggest_post_processor` handler
- Updated documentation
- Tested end-to-end workflow

---

## Phase Summary

| Phase | Goal | Key Deliverable |
|-------|------|-----------------|
| 1 | CAM State Access | `get_cam_state`, `get_tool_library` |
| 2 | Geometry Analysis | `analyze_geometry_for_cam` |
| 3 | Stock Suggestions | `suggest_stock_setup` + SQLite |
| 4 | Toolpath Strategy | `suggest_toolpath_strategy` |
| 5 | Learning System | `record_user_choice` + feedback loop |
| 6 | Polish | `suggest_post_processor` + docs |

---

## Future Milestones (Out of Scope for MVP)

### Milestone 2: Real-Time Observation
- Hook into Fusion UI events
- Detect when user enters CAM workspace
- Proactively offer suggestions
- Observe user's actual operations

### Milestone 3: Advanced Learning
- Machine learning model for predictions
- Cross-part pattern recognition
- Shop-wide preference sharing
- A/B testing suggestion strategies

### Milestone 4: Simulation Integration
- Analyze toolpath simulation results
- Detect potential collisions
- Suggest parameter adjustments
- Estimate cycle time

---

*Last updated: 2026-02-04*
