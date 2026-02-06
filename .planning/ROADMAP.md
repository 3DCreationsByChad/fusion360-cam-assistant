# Fusion 360 AI CAM Assistant — Roadmap

**GitHub:** https://github.com/3DCreationsByChad/fusion360-cam-assistant

## Milestone 1: CAM Extension MVP

**Goal:** Extend Fusion-360-MCP-Server with core CAM operations that analyze geometry and provide basic suggestions.

**Success Criteria:**
- Can query current CAM state from Fusion 360
- Can analyze geometry and return CAM-relevant features
- Can suggest stock setup based on bounding box
- Can query tool library
- Preferences stored in SQLite

---

## Phase 1: Foundation — CAM State Access ✓

**Goal:** Establish basic CAM API access and state querying with explicit units in all responses.

**Status:** COMPLETE (2026-02-05)

**Plans:** 1 plan

Plans:
- [x] 01-01-PLAN.md — Enhance CAM operations with explicit units and full tool properties

### Deliverables
- [x] `cam_operations.py` with `get_cam_state`, `get_tool_library` using explicit unit format
- [x] WCS information per setup
- [x] Full tool property definitions
- [x] Human-verified in Fusion 360

---

## Phase 2: Geometry Analysis ✓

**Goal:** Analyze part geometry to extract CAM-relevant information with rich metadata, confidence scoring, machining priority grouping, and orientation suggestions.

**Status:** COMPLETE (2026-02-05)

**Plans:** 3 plans

Plans:
- [x] 02-01-PLAN.md — Feature detection foundation using Fusion RecognizedHole/RecognizedPocket APIs
- [x] 02-02-PLAN.md — Feature classification with slot heuristics, confidence scoring, and priority grouping
- [x] 02-03-PLAN.md — Orientation analysis with setup sequences and minimum tool radius

### Deliverables
- [x] `geometry_analysis/` module with FeatureDetector, OrientationAnalyzer, confidence scoring
- [x] Features detected via Fusion CAM APIs with entityTokens for programmatic selection
- [x] Slots classified using aspect ratio heuristic (>3.0)
- [x] Confidence scores (0-1) with reasoning text on every feature
- [x] Features grouped by machining priority (drilling, roughing, finishing)
- [x] Orientation suggestions with setup/flip sequences
- [x] Minimum tool radius (global and recommended with 80% rule)

---

## Phase 3: Stock Suggestions ✓

**Goal:** Suggest stock setup based on geometry analysis with standard size rounding, orientation recommendations, and preference storage with source attribution.

**Status:** COMPLETE (2026-02-05)

**Plans:** 3 plans

Plans:
- [x] 03-01-PLAN.md — Stock calculation utilities with standard size tables
- [x] 03-02-PLAN.md — Cylindrical detection and SQLite preference storage
- [x] 03-03-PLAN.md — suggest_stock_setup handler with prompting logic

### Deliverables
- [x] `stock_suggestions/` module with stock calculator and standard size tables
- [x] Cylindrical part detection with trade-off options
- [x] SQLite schema (cam_stock_preferences, cam_machine_profiles)
- [x] `suggest_stock_setup` handler with preference prompting
- [x] Source attribution on all suggestions
- [x] Human-verified in Fusion 360

---

## Phase 4: Toolpath Strategy Suggestions ✓

**Goal:** Recommend toolpath strategies based on geometry and material with per-feature operation mapping, tool selection, and feeds/speeds calculation.

**Status:** COMPLETE (2026-02-05)

**Plans:** 2 plans

Plans:
- [x] 04-01-PLAN.md — Toolpath strategy rules engine (material library, feeds/speeds, tool selector, operation mapper)
- [x] 04-02-PLAN.md — Strategy preferences, MCP handler integration, and Fusion 360 verification

### Deliverables
- [x] `toolpath_strategy/` module with rules engine (material_library, feeds_speeds, tool_selector, operation_mapper)
- [x] `suggest_toolpath_strategy` MCP handler with per-feature recommendations
- [x] `cam_strategy_preferences` SQLite table for strategy preferences
- [x] Tool selection with 80% corner radius rule and flute length constraints
- [x] Feeds/speeds from standard SFM formulas with carbide/HSS support
- [x] Human-verified in Fusion 360

---

## Phase 5: Learning System

**Goal:** Build a feedback loop that captures user decisions and uses historical patterns to improve future CAM suggestions with exponential decay weighting and interpretable acceptance rates.

**Status:** PLANNED

**Plans:** 2 plans

Plans:
- [ ] 05-01-PLAN.md — Feedback learning module foundation (SQLite storage, recency weighting, confidence adjustment, context matching)
- [ ] 05-02-PLAN.md — MCP handlers, learning integration into existing operations, and Fusion 360 verification

### Deliverables
- [ ] `feedback_learning/` module with feedback store, recency weighting, confidence adjuster, and context matcher
- [ ] `record_user_choice` MCP handler for capturing implicit and explicit feedback
- [ ] `get_feedback_stats`, `export_feedback_history`, `clear_feedback_history` MCP handlers
- [ ] Learning integration in `suggest_stock_setup` and `suggest_toolpath_strategy`
- [ ] Full tool_description documentation for AI client discovery
- [ ] Human-verified in Fusion 360

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

*Last updated: 2026-02-05*
