# Fusion 360 AI Assistant

## What This Is

An AI-powered overlay for Fusion 360 that watches your UI interactions and suggests optimal CAM workflows—specifically for stock setup, toolpath strategy, and post-processing. It learns from your preferences and asks for feedback to improve future suggestions.

## Core Value

The toolpath strategy suggestion matches what you would have chosen, saving you decision time while maintaining quality.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Overlay integrates with Fusion 360 UI to observe interactions in real-time
- [ ] Detects part geometry and suggests stock orientation based on historical preferences
- [ ] Recommends toolpath strategy (roughing/finishing approach) for current geometry
- [ ] Suggests post-processing settings based on machine profile and material
- [ ] Maintains preference memory across sessions with explicit feedback loop

### Out of Scope

- Direct automation that executes without user confirmation — this is a suggestion engine, not a robot
- Physical machine control via G-code execution — stays at recommendation level
- Standalone CAD modeling features — purely CAM workflow assist within Fusion 360

## Context

You want an intelligent assistant that reduces cognitive load during Fusion 360 CAM setup by:
- Observing which UI elements you interact with
- Cross-referencing your historical preferences (orientations, tooling, workholding)
- Offering targeted suggestions at the right moment in your workflow
- Learning from your feedback to improve future recommendations

The system runs locally using your local AI models, ensuring data stays on your machine.

## Constraints

- **Tech**: Fusion 360 API integration, local AI models (no cloud dependency)
- **Safety**: All actions require user confirmation—suggest only, never auto-execute
- **Scope**: CAM workflow assistance only, not part design or simulation

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Suggestion-only approach | Safety first — CAM errors are expensive; you confirm each action | Lower risk, higher trust |
| Local AI models only | Data privacy, no API costs, works offline | Self-contained solution |
| Preference memory + feedback loop | Builds accuracy over time while respecting your expertise | Adaptive but not prescriptive |

---
*Last updated: 2026-02-04 after initialization*
