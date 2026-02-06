---
phase: 03-stock-suggestions
plan: 03
subsystem: stock-suggestions
tags: [mcp-handler, stock-setup, preference-prompting, orientation]

dependency_graph:
  requires:
    - 03-01 (stock calculator)
    - 03-02 (cylindrical detection, preference store)
  provides:
    - suggest_stock_setup MCP operation
  affects:
    - Phase 4 (toolpath strategy can build on stock context)

tech_stack:
  added: []
  patterns:
    - Three-status response pattern (success, preference_needed, orientation_choice_needed)
    - Relative imports for Fusion add-in package context

key_files:
  created: []
  modified:
    - Fusion-360-MCP-Server/cam_operations.py
    - Fusion-360-MCP-Server/mcp_integration.py

decisions:
  - id: orientation-confidence-threshold
    choice: "0.70 threshold — below this, prompt user to choose"
    reason: "Avoids committing to uncertain orientation without user input"
  - id: close-alternatives-threshold
    choice: "15% score gap for showing alternatives"
    reason: "Surface viable options without overwhelming with noise"
  - id: three-status-responses
    choice: "success / preference_needed / orientation_choice_needed"
    reason: "Interactive prompting per CONTEXT.md — never silently default"
  - id: relative-imports
    choice: "from .stock_suggestions import ... (relative)"
    reason: "Required for Fusion add-in package context — absolute imports fail"
  - id: tool-readme-documentation
    choice: "Full parameter docs in tool_description variable"
    reason: "MCP AI clients only call operations documented in tool_readme"
  - id: directory-junction-deployment
    choice: "Junction from AppData bundle to git repo"
    reason: "Fusion loads add-in from AppData, not git repo — junction keeps in sync"

metrics:
  completed: 2026-02-05
---

# Phase 03 Plan 03: MCP Tool Integration Summary

suggest_stock_setup handler with interactive prompting and deployment fixes.

## One-liner

suggest_stock_setup MCP handler with three response statuses, tool_readme documentation, relative imports, and directory junction deployment.

## What Was Implemented

### Task 1: handle_suggest_stock_setup handler

Added to `cam_operations.py` (~200 lines):

1. **Full handler** combining all Phase 3 utilities:
   - `calculate_stock_dimensions` from 03-01
   - `detect_cylindrical_part`, `get_preference`, `classify_geometry_type` from 03-02
   - `OrientationAnalyzer` from Phase 2

2. **Three response statuses** per CONTEXT.md:
   - `"success"` — full stock suggestion with dimensions, orientation, setup_sequence
   - `"preference_needed"` — prompts user when no stored preference exists
   - `"orientation_choice_needed"` — prompts when confidence < 0.70

3. **Response includes**: stock_dimensions, recommended_shape, orientation with score, setup_sequence, offsets_applied, source attribution, close alternatives within 15%

### Task 2: Human Verification (Deployment Fixes Required)

Verification revealed three deployment issues that were fixed:

1. **tool_readme said "coming soon"** — AI clients wouldn't call the operation because the MCP tool documentation still marked it as unimplemented. Fixed by replacing "coming soon" with full parameter documentation in `mcp_integration.py`.

2. **No deployment to Fusion add-in** — All code existed only in the git repo. Fusion 360 loads add-ins from `AppData\Roaming\Autodesk\ApplicationPlugins\MCP-link.bundle\Contents\`. Fixed by creating a directory junction from the bundle Contents to the git repo.

3. **Absolute imports failed in package context** — `from stock_suggestions import ...` failed because `cam_operations.py` is loaded as a package member via `from . import cam_operations`. Fixed by changing to relative imports: `from .stock_suggestions import ...` and `from .geometry_analysis import ...`.

After fixes, verification passed:
- No-args call → `"orientation_choice_needed"` (correct — low confidence)
- With `selected_orientation: "Z_UP"` → `"success"` with full stock recommendation
- Response included stock_dimensions, recommended_shape, orientation, setup_sequence, offsets, source attribution

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Orientation confidence threshold | 0.70 | Below this, prompt user rather than guess |
| Close alternatives threshold | 15% score gap | Surface viable options without noise |
| Response statuses | 3 types | Interactive prompting — never silent defaults |
| Import style | Relative (from .) | Required for Fusion add-in package loading |
| Deployment | Directory junction | Keeps git repo and running add-in in sync |

## Commits

| Hash | Type | Description |
|------|------|-------------|
| f9efa9a | feat | Implement suggest_stock_setup MCP handler |
| (pending) | fix | Relative imports, tool_readme docs, deployment junction |

## Deviations from Plan

1. **Deployment gap discovered** — Plan assumed code in git repo would be loaded by Fusion. In reality, Fusion loads from AppData. Required directory junction setup.
2. **Import style change** — Plan used absolute imports. Package context required relative imports.
3. **tool_readme update needed** — Plan didn't account for MCP tool discoverability requiring documentation update.

## Files Modified

```
Fusion-360-MCP-Server/
├── cam_operations.py          - handle_suggest_stock_setup + relative imports
└── mcp_integration.py         - tool_readme documentation for suggest_stock_setup
```

## Deployment Setup

```
C:\Users\cdeit\AppData\Roaming\Autodesk\ApplicationPlugins\MCP-link.bundle\Contents\
    → Junction → C:\Users\cdeit\fusion360-cam-assistant\Fusion-360-MCP-Server\
```

Code changes in git repo are now live. Restart add-in in Fusion to pick up changes.

## Lessons Learned

1. **MCP tool discoverability is documentation-driven** — AI clients only call operations documented in tool_readme. "Coming soon" = invisible.
2. **Fusion add-in loads from AppData, not working directory** — Always verify deployment path matches development path.
3. **Package-relative imports required** — When loaded via `from . import module`, sub-imports must also be relative.
