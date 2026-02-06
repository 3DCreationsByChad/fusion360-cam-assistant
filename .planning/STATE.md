# Project State

**Last Updated:** 2026-02-05
**Phase:** 3 - Stock Suggestions
**Status:** Complete

## Current Position

Phase: 3 of 5 (Stock Suggestions)
Plan: 03 of 03 in phase
Status: Complete
Last activity: 2026-02-05 - Phase 3 verified in Fusion 360

Progress: [########--] 80% (8/10 plans estimated)

### Phase 3 Progress

| Plan | Name | Status |
|------|------|--------|
| 03-01 | Stock calculation foundation | Complete |
| 03-02 | Cylindrical detection and preference store | Complete |
| 03-03 | MCP tool integration | Complete |

### What Was Delivered (Phase 3)

1. **stock_suggestions module** with stock calculator, standard size tables, cylindrical detection, preference store
2. **suggest_stock_setup MCP operation** — callable via MCP protocol, returns stock dimensions with orientation
3. **Three interactive response types**: success, preference_needed, orientation_choice_needed
4. **SQLite preference storage** via cam_stock_preferences and cam_machine_profiles tables
5. **Deployment junction** from Fusion AppData to git repo for live code updates

### Key Deployment Discovery

Fusion 360 loads add-ins from `AppData\Roaming\Autodesk\ApplicationPlugins\`, NOT the git repo. A directory junction now links the two. MCP tool discoverability requires operations to be documented in tool_description — "coming soon" makes operations invisible to AI clients.

## Accumulated Decisions

| Phase | Decision | Rationale |
|-------|----------|-----------|
| 01-01 | Explicit unit format `{"value": X, "unit": "mm"}` | Prevents ambiguity in all responses |
| 01-01 | Use `tool.toJson()` for document library | API returns objects not dicts |
| 01-01 | Extract stock via `setup.parameters` | StockModes enum doesn't exist |
| 02-01 | Keep face_features for backward compatibility | Preserve existing face-type detection |
| 02-01 | Feature detection source indicator | Shows fusion_api vs face_analysis method |
| 02-01 | Confidence/reasoning per feature | Per CONTEXT.md requirements |
| 02-02 | Slot threshold: aspect_ratio > 3.0 | Distinguishes slots from pockets |
| 02-02 | Ambiguous range: 2.5-3.5 aspect_ratio | Flags uncertain classifications |
| 02-02 | needs_review threshold: confidence < 0.80 | Flags low-confidence features |
| 02-02 | Priority: drilling < 12mm, roughing > 10mm | Machining operation ordering |
| 02-03 | Scoring weights: 60/30/10 (access/setup/stability) | Per RESEARCH.md recommendation |
| 02-03 | Conservative accessibility analysis | Assume reachable unless clearly flagged |
| 02-03 | 80% rule for tool radius | Industry standard for internal corners |
| 03-01 | XY offset applied to all 4 sides (2x per axis) | Standard practice for facing material |
| 03-01 | Z offset applied to top only (1x) | Bottom typically fixture reference surface |
| 03-02 | Combined scoring: 60% face + 40% bbox shape | Balance direct geometry with bounding box analysis |
| 03-02 | 20% tolerance for cross-section similarity | Dimensions within 20% considered "similar" |
| 03-02 | 70% threshold for dominant feature type | classify_geometry_type categorization threshold |
| 03-02 | Lowercase normalization for preference keys | Consistent keying for material + geometry_type |
| 03-03 | Orientation confidence threshold: 0.70 | Below this, prompt user to choose |
| 03-03 | Close alternatives threshold: 15% score gap | Surface viable options without noise |
| 03-03 | Relative imports for add-in package context | Absolute imports fail when loaded via from . import |
| 03-03 | tool_readme documentation required for discoverability | AI won't call undocumented operations |

## Lessons Learned

### Phase 1
1. **Document tool library returns API objects, not dicts** - Use `tool.toJson()` to parse
2. **`cam.activeSetup` doesn't exist** - Use `setup.isActive` or skip
3. **`adsk.cam.StockModes` enum doesn't exist** - Extract stock via `setup.parameters`
4. **Stock/tool dimensions in document format are already in mm** - No conversion needed

### Phase 2
1. **RecognizedHole/RecognizedPocket may not be available in all Fusion versions** - Use try/except
2. **entityToken provides face references for CAM selection** - Store in fusion_faces list
3. **Graceful import fallback pattern** - FEATURE_DETECTOR_AVAILABLE flag for optional modules
4. **Aspect ratio for slot classification** - max(L,W)/min(L,W) > 3.0 is slot
5. **Modular confidence scoring** - Separate module enables reuse across feature types
6. **Weighted orientation scoring** - Provides ranked alternatives for workholding planning
7. **Conservative accessibility** - Better to assume reachable than over-flag as unreachable

### Phase 3
1. **Fusion API coordinates in cm** - Multiply by 10 to convert to mm
2. **MCP bridge SQLite calls** - Use tool_unlock_token "29e63eb5" for sqlite tool
3. **Source attribution pattern** - Include "source" key in preference returns for traceability
4. **MCP tool discoverability is documentation-driven** - "Coming soon" = invisible to AI
5. **Fusion loads add-ins from AppData, not working directory** - Must deploy or symlink
6. **Package-relative imports required** - from .module when loaded via from . import

## Session Continuity

Last session: 2026-02-05
Stopped at: Phase 3 complete, ready for Phase 4
Resume file: None

## Next Steps

Phase 4: Toolpath Strategy Suggestions
- suggest_toolpath_strategy handler
- Rules engine for feature-to-operation mapping
- Strategy preferences table

Command: `/gsd:plan-phase 4`
