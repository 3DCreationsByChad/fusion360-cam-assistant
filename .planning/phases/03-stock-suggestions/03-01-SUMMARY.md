---
phase: 03-stock-suggestions
plan: 01
subsystem: stock-suggestions
tags: [stock-calculation, unit-conversion, metric, imperial]

dependency_graph:
  requires: []
  provides:
    - stock_suggestions module
    - standard size tables (metric/imperial)
    - round_to_standard_size function
    - calculate_stock_dimensions function
  affects:
    - 03-02 (stock type detection)
    - 03-03 (MCP tool integration)

tech_stack:
  added: []
  patterns:
    - explicit unit format {"value": X, "unit": "mm"}
    - Fusion API cm to mm conversion (* 10)

key_files:
  created:
    - Fusion-360-MCP-Server/stock_suggestions/__init__.py
    - Fusion-360-MCP-Server/stock_suggestions/stock_sizes.py
    - Fusion-360-MCP-Server/stock_suggestions/stock_calculator.py
  modified: []

decisions:
  - id: xy-offset-both-sides
    choice: "XY offset applied to all 4 sides (2x per axis)"
    reason: "Standard machining practice - material needed on all sides for facing"
  - id: z-offset-top-only
    choice: "Z offset applied to top only"
    reason: "Bottom face typically reference surface against fixture"

metrics:
  duration: 165s
  completed: 2026-02-05
---

# Phase 03 Plan 01: Stock Calculation Foundation Summary

Stock dimension calculation with standard size tables and configurable offsets.

## One-liner

Stock calculator with metric/imperial size tables, 5mm XY + 2.5mm Z offsets, rounds to standard supplier sizes.

## What Was Implemented

### Task 1: Stock Sizes Module

Created `stock_suggestions/stock_sizes.py` with:

1. **Metric Size Tables:**
   - `METRIC_PLATE_THICKNESSES_MM` - 27 standard thicknesses (3mm to 100mm)
   - `METRIC_BAR_WIDTHS_MM` - 33 standard widths (10mm to 300mm)
   - `METRIC_ROUND_DIAMETERS_MM` - 35 standard diameters (6mm to 150mm)

2. **Imperial Size Tables:**
   - `IMPERIAL_PLATE_THICKNESSES_IN` - 19 standard thicknesses (1/8" to 4")
   - `IMPERIAL_BAR_WIDTHS_IN` - 26 standard widths (1/2" to 12")
   - `IMPERIAL_ROUND_DIAMETERS_IN` - 23 standard diameters (1/4" to 4")

3. **round_to_standard_size() function:**
   - Rounds dimension UP to next available standard size
   - Supports metric and imperial unit systems
   - Handles width, thickness, and round_diameter types
   - Imperial: converts mm->in, finds size, converts back to mm

### Task 2: Stock Calculator Module

Created `stock_suggestions/stock_calculator.py` with:

1. **DEFAULT_OFFSETS constant:**
   ```python
   DEFAULT_OFFSETS = {
       "xy_mm": 5.0,   # Per CONTEXT.md: 5mm XY offset (all 4 sides)
       "z_mm": 2.5     # Per CONTEXT.md: 2.5mm Z offset (top only)
   }
   ```

2. **calculate_stock_dimensions() function:**
   - Input: Fusion 360 BoundingBox3D
   - Converts cm coordinates to mm (* 10)
   - Applies XY offset on all 4 sides (total = 2 * xy_mm per axis)
   - Applies Z offset on top only (single z_mm)
   - Rounds to standard sizes when enabled
   - Returns explicit unit format: `{"value": X, "unit": "mm"}`

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| XY offset application | Both sides (2x) | Standard practice - material on all sides for facing |
| Z offset application | Top only (1x) | Bottom typically fixture reference surface |
| Unit format | `{"value": X, "unit": "mm"}` | Consistent with Phase 1 decision for clarity |
| Size table defaults | Return largest if exceeded | Safe default - ensures adequate material |

## Commits

| Hash | Type | Description |
|------|------|-------------|
| a9b16cb | feat | Create stock sizes module with standard size tables |
| 04915cd | feat | Create stock calculator with offset application |

## Verification Results

```
Import test: OK
DEFAULT_OFFSETS matches CONTEXT.md: OK
round_to_standard_size(45.5, metric, width) = 50.0: OK
round_to_standard_size(1.1", imperial, width) = 28.575mm: OK
```

## Deviations from Plan

None - plan executed exactly as written.

## Files Created

```
Fusion-360-MCP-Server/stock_suggestions/
├── __init__.py           (45 lines) - Module exports
├── stock_sizes.py        (134 lines) - Size tables and rounding
└── stock_calculator.py   (126 lines) - Dimension calculation
```

## Next Phase Readiness

Ready for 03-02:
- stock_suggestions module is importable
- round_to_standard_size available for stock type detection
- calculate_stock_dimensions ready for integration

No blockers identified.
