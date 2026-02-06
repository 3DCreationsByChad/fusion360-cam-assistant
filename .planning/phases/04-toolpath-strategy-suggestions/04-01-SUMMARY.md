---
phase: 04-toolpath-strategy-suggestions
plan: 01
subsystem: cam-intelligence
tags: [python, cnc, machining, feeds-speeds, material-database, tool-selection]

# Dependency graph
requires:
  - phase: 02-feature-detection
    provides: Feature detection with geometry analysis
provides:
  - Material property database with SFM and chip load values for 6 common materials
  - Feeds/speeds calculator using industry-standard formulas
  - Tool selector with 80% corner radius rule and flute length constraints
  - Operation mapper with feature-to-operation rules (hole, pocket, slot)
affects: [04-02-toolpath-integration, phase-5-operation-creation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Explicit unit format: {\"value\": X, \"unit\": \"mm\"} on all dimensional outputs"
    - "Confidence + reasoning pattern: All recommendations include confidence (0-1) and reasoning string"
    - "Source attribution: All lookups include \"source\" key for traceability"
    - "Graceful defaults: Unknown inputs get conservative fallbacks, never raise errors"
    - "Lowercase normalization: All lookup keys normalized to lowercase with underscores"

key-files:
  created:
    - Fusion-360-MCP-Server/toolpath_strategy/__init__.py
    - Fusion-360-MCP-Server/toolpath_strategy/material_library.py
    - Fusion-360-MCP-Server/toolpath_strategy/feeds_speeds.py
    - Fusion-360-MCP-Server/toolpath_strategy/tool_selector.py
    - Fusion-360-MCP-Server/toolpath_strategy/operation_mapper.py
  modified: []

key-decisions:
  - "SFM values from research: aluminum (400/1200), mild_steel (100/300), stainless_steel (40/120), brass (300/900), plastic (500/1500), wood (600/1800)"
  - "Chip load ranges in inches/tooth for precision with imperial-based SFM formula"
  - "RPM cap at 24000 (typical spindle maximum) to prevent over-speed recommendations"
  - "Stepover percentages: 45% roughing (midpoint of 40-50%), 15% finishing (midpoint of 10-20%)"
  - "Stepdown: 1.0x tool diameter (midpoint of 0.5-1.5x range)"
  - "Priority system for operations: 1=drilling, 2=roughing, 3=finishing"
  - "Partial material matching: \"6061 aluminum\" matches \"aluminum\", \"304 stainless\" matches \"stainless_steel\""

patterns-established:
  - "Material lookup with progressive fallback: exact match → partial match → word overlap → conservative defaults"
  - "Tool selection with dual constraints: 80% corner radius rule AND flute length >= depth * 1.2"
  - "Operation mapping with lambda conditions evaluated at runtime for flexible rule system"
  - "Roughing + finishing recommendations per feature (not just roughing)"
  - "Detailed reasoning strings explain why recommendations were made"

# Metrics
duration: 4min
completed: 2026-02-05
---

# Phase 04 Plan 01: Toolpath Strategy Rules Engine Summary

**Pure-Python toolpath intelligence: material database, feeds/speeds calculator, 80% tool selector, and feature-to-operation mapper with confidence scoring**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-05T22:09:18Z
- **Completed:** 2026-02-05T22:13:47Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Material property database with 6 materials (aluminum, mild_steel, stainless_steel, brass, plastic, wood) and intelligent partial matching
- Feeds/speeds calculator using industry formulas: RPM = (SFM * 3.82) / diameter_inches, Feed = RPM * flutes * chip_load
- Tool selector implementing 80% corner radius rule with flute length constraint (depth * 1.2 safety margin)
- Operation mapper with conditional rules for holes (12mm threshold), pockets (10mm depth threshold), and slots
- All outputs use explicit unit format with confidence scoring and reasoning

## Task Commits

Each task was committed atomically:

1. **Task 1: Create material library and feeds/speeds calculator** - `bc12957` (feat)
2. **Task 2: Create tool selector and operation mapper** - `6801d75` (feat)

## Files Created/Modified

- `Fusion-360-MCP-Server/toolpath_strategy/__init__.py` - Module exports with clean imports
- `Fusion-360-MCP-Server/toolpath_strategy/material_library.py` - Material database with SFM/chip-load values and partial matching lookup
- `Fusion-360-MCP-Server/toolpath_strategy/feeds_speeds.py` - RPM, feed rate, stepover, stepdown calculator
- `Fusion-360-MCP-Server/toolpath_strategy/tool_selector.py` - Largest fitting tool selector with 80% rule and flute length constraint
- `Fusion-360-MCP-Server/toolpath_strategy/operation_mapper.py` - Feature-to-operation mapping with roughing + finishing recommendations

## Decisions Made

**Material Database Structure:**
- SFM values for both HSS and carbide tooling (3x multiplier for carbide matches research)
- Chip load ranges in inches/tooth to align with imperial-based SFM formula
- Hardness classification (soft/medium/hard) for material-aware operation selection
- Conservative defaults (SFM 100/300, chip_load 0.0005-0.001) for unknown materials

**Feeds/Speeds Calculations:**
- RPM cap at 24000 to prevent exceeding typical spindle limits
- Chip load selection: midpoint for roughing, 70% of minimum for finishing
- Stepover: 45% diameter (roughing), 15% diameter (finishing)
- Stepdown: 1.0x diameter (balanced between 0.5-1.5x range)

**Tool Selection Logic:**
- 80% corner radius rule enforced (industry standard for internal corners)
- Flute length must be >= depth * 1.2 (20% safety margin)
- Select largest fitting tool (maximizes material removal rate)
- Detailed constraint reporting when no tools fit

**Operation Mapping:**
- Drilling for holes < 12mm diameter (from Phase 2 decision)
- Adaptive clearing for deep pockets (> 10mm) in medium/hard materials
- 2D pocket for shallow pockets or soft materials
- Both roughing AND finishing operations recommended per feature
- Priority system ensures correct machining sequence

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all modules created successfully with expected functionality.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for Plan 02 (MCP Integration):**
- Complete toolpath_strategy module with all 4 components
- All functions use relative imports (compatible with Fusion add-in package loading)
- Explicit unit format on all outputs (integrates with existing MCP response pattern)
- Confidence + reasoning on all recommendations (matches established Phase 2/3 pattern)
- No Fusion API dependencies (pure calculation modules, independently testable)

**No blockers or concerns.**

---
*Phase: 04-toolpath-strategy-suggestions*
*Completed: 2026-02-05*
