# Fusion 360 AI CAM Assistant

**GitHub:** https://github.com/3DCreationsByChad/fusion360-cam-assistant

## What This Is

An AI-powered CAM workflow assistant for Fusion 360 that analyzes geometry, suggests optimal stock setup, toolpath strategies, and post-processing settings. Built as an extension to the [Fusion-360-MCP-Server](https://github.com/AuraFriday/Fusion-360-MCP-Server), it learns from your preferences and improves suggestions over time.

## Core Value

The assistant suggests CAM workflows that match what you would have chosen, saving decision time while maintaining quality. It learns your preferences for tools, strategies, and machine settings.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Analyze part geometry and extract CAM-relevant features (pockets, holes, contours)
- [ ] Suggest stock setup (dimensions, offsets, orientation) based on geometry + preferences
- [ ] Recommend toolpath strategy (roughing/finishing approach) for current geometry
- [ ] Query and suggest tools from Fusion's tool library
- [ ] Suggest post-processor based on machine profile
- [ ] Store and learn from user preferences via SQLite
- [ ] Record user choices to improve future suggestions

### Out of Scope

- Direct automation that executes without user confirmation — suggestion engine only
- Physical machine control via G-code execution — stays at recommendation level
- CAD modeling features — purely CAM workflow assist
- Real-time UI observation (deferred to future milestone)

## Context

You want an intelligent assistant that reduces cognitive load during Fusion 360 CAM setup by:
- Analyzing part geometry to understand manufacturability
- Cross-referencing your historical preferences (orientations, tooling, feeds/speeds)
- Offering targeted suggestions via MCP protocol to your AI assistant
- Learning from your feedback to improve future recommendations

The system runs locally using the MCP protocol, connecting your local AI to Fusion 360.

## Technical Approach

### Foundation: Fusion-360-MCP-Server

Discovered existing open-source MCP server that provides:
- Generic Fusion 360 API access via MCP protocol
- Python execution with full `adsk.core`, `adsk.fusion`, `adsk.cam` access
- Thread-safe architecture (main thread enforcement)
- SQLite integration for data storage
- Auto-reconnect with exponential backoff

**Repository:** `Fusion-360-MCP-Server/` (cloned locally)

### Extension Strategy

Rather than building from scratch, extend the MCP server with CAM-specific operations:

```
AI Assistant (Claude/Local LLM)
         │
         ▼
    MCP-Link Server
         │
         ▼
┌────────────────────────────┐
│  Fusion 360 MCP Add-in     │
├────────────────────────────┤
│  EXISTING        │  NEW    │
│  • Generic API   │  • analyze_geometry_for_cam
│  • Python exec   │  • suggest_stock_setup
│  • Scripts       │  • suggest_toolpath_strategy
│  • Docs lookup   │  • get_cam_state
│                  │  • record_user_choice
│                  │  • get_tool_library
│                  │  • suggest_post_processor
└────────────────────────────┘
         │
         ▼
    Fusion 360 CAM API (adsk.cam)
```

### Data Storage

SQLite tables via existing MCP sqlite tool:
- `cam_stock_preferences` — learned stock offsets, orientations
- `cam_strategy_preferences` — preferred operations per feature type
- `cam_feedback_history` — suggestion vs. actual choice for learning
- `cam_machine_profiles` — machine configs, post processors

## Constraints

- **Tech**: Extend Fusion-360-MCP-Server, use `adsk.cam` API, SQLite for storage
- **Safety**: All suggestions require user confirmation—never auto-execute
- **Scope**: CAM workflow assistance only, not CAD design
- **Local**: No cloud dependencies, runs entirely on local machine

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Extend MCP Server | Existing foundation handles protocol, threading, API access | Faster development, proven architecture |
| Suggestion-only | CAM errors are expensive; user confirms each action | Lower risk, higher trust |
| SQLite preferences | Already integrated via MCP, simple schema | Easy persistence, queryable history |
| Phase-based implementation | Validate core functionality before adding learning | Ship early, iterate on feedback |

## Key Files

| File | Purpose |
|------|---------|
| `Fusion-360-MCP-Server/mcp_integration.py` | Core MCP infrastructure, add CAM operations here |
| `Fusion-360-MCP-Server/lib/mcp_client.py` | Protocol layer (no changes needed) |
| `Fusion-360-MCP-Server/CAM_EXTENSION_DESIGN.md` | Detailed extension architecture |
| `.planning/ROADMAP.md` | Implementation phases |

---
*Last updated: 2026-02-04 after discovering Fusion-360-MCP-Server foundation*
