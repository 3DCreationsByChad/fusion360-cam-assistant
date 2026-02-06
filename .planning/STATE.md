# Project State

**Last Updated:** 2026-02-05
**Phase:** 4 - Toolpath Strategy Suggestions
**Status:** Phase Complete

## Current Position

Phase: 4 of 5 (Toolpath Strategy Suggestions)
Plan: 02 of 02 in phase
Status: Phase complete
Last activity: 2026-02-05 - Completed 04-02-PLAN.md (strategy preferences and MCP handler)

Progress: [##########] 100% (10/10 plans estimated)

### Phase 4 Progress

| Plan | Name | Status |
|------|------|--------|
| 04-01 | Toolpath strategy rules engine | Complete |
| 04-02 | Strategy preferences and MCP handler | Complete |

### What Was Delivered (Phase 4)

**Plan 01 - Toolpath strategy rules engine:**
1. **toolpath_strategy module** with material_library, feeds_speeds, tool_selector, operation_mapper
2. **Material database** with 6 materials (aluminum, mild_steel, stainless_steel, brass, plastic, wood) and partial matching
3. **Feeds/speeds calculator** using industry formulas: RPM = (SFM * 3.82) / diameter_inches
4. **Tool selector** with 80% corner radius rule and flute length constraint (depth * 1.2)
5. **Operation mapper** with conditional rules for holes (12mm threshold), pockets (10mm depth), slots

**Plan 02 - Strategy preferences and MCP handler:**
1. **suggest_toolpath_strategy MCP operation** processing features in priority order with per-feature recommendations
2. **cam_strategy_preferences SQLite table** for storing and retrieving user strategy choices
3. **Strategy preferences module** with get/save/initialize functions following SQLite bridge pattern
4. **Tool_description documentation** enabling AI client discovery of suggest_toolpath_strategy
5. **Three response statuses** (success, no_features, no_tool_available) with graceful error handling

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
| 04-01 | Stepover percentages: 45% roughing, 15% finishing | Midpoint of research ranges (40-50% and 10-20%) |
| 04-01 | Stepdown: 1.0x tool diameter | Midpoint of 0.5-1.5x research range |
| 04-01 | RPM cap at 24000 | Typical spindle maximum for consumer CNC |
| 04-01 | Chip load ranges in inches/tooth | Aligns with imperial-based SFM formula |
| 04-01 | Priority system: 1=drilling, 2=roughing, 3=finishing | Ensures correct machining sequence |
| 04-01 | Partial material matching with word overlap | "6061 aluminum" matches "aluminum" |
| 04-02 | Three response statuses for strategy suggestions | success, no_features, no_tool_available per feature |
| 04-02 | Tool type filter for drilling operations | "drill" for holes, None for roughing/finishing |
| 04-02 | Feature processing priority order | drilling -> roughing -> finishing |
| 04-02 | User preference override mechanism | Stored preferences replace default rules |
| 04-02 | Source attribution for recommendations | Tracks default_rules vs user_preference origin |

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

### Phase 4
1. **MCP handler pattern for CAM operations** - Import guard, feature analysis, preference check, tool selection, feeds/speeds
2. **Per-feature recommendations structure** - Roughing/finishing ops, tool selection with 80% rule, cutting parameters
3. **Graceful tool selection failures** - Continue processing other features when no tool fits
4. **AI client caching of tool_description** - Restart both add-in and client after documentation updates
5. **Priority-based feature processing** - Ensures correct machining workflow (drill, rough, finish)

## Session Continuity

Last session: 2026-02-05
Stopped at: Phase 4 complete (toolpath strategy suggestions)
Resume file: None

## Next Steps

Phase 5: Learning System
- record_user_choice MCP operation for capturing user corrections
- Learning system to improve recommendations based on user feedback
- Confidence scoring improvements

Command: `/gsd:research 5` to research Phase 5, then `/gsd:plan 05-01`
