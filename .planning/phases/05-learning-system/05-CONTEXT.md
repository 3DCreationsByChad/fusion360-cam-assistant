# Phase 5: Learning System - Context

**Gathered:** 2026-02-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a feedback loop that captures user decisions and uses that history to improve future CAM suggestions across all operations (stock setup, toolpath strategy, tool selection). This is about building the feedback mechanism and integration logic — not expanding what we suggest.

Delivers:
- `record_user_choice` MCP operation for capturing implicit and explicit feedback
- `cam_feedback_history` SQLite table for storing feedback events
- Learning logic that influences future suggestions based on past patterns
- Feedback statistics and export capabilities

</domain>

<decisions>
## Implementation Decisions

### Feedback Capture Timing
- **Record immediately on selection** — As soon as user picks something different from suggestion, write to SQLite
- **Optional explicit feedback via MCP operation** — `record_feedback(good/bad, optional_note)` for AI client to call
- **Optional note field on implicit feedback** — Allow attaching reason why user changed suggestion, but don't require it
- **Write immediately, no batching** — Each feedback event writes to SQLite immediately to prevent data loss on crashes
- **Capture with each record:**
  - Context snapshot (material, geometry_type, feature dimensions, part size)
  - Full suggestion payload (entire JSON that was suggested)
  - User's actual choice (what they selected instead)
  - Timestamp (for recency weighting)

### Learning Influence Scope
- **Material-wide patterns** — If user always picks larger stock for aluminum, apply that pattern to all aluminum parts
- **Separate learning per suggestion type** — Stock preferences don't influence toolpath suggestions; each has its own feedback history
- **All matching history weighted by recency** — Use all past decisions for material+geometry, weight recent ones higher
- **Show conflicting choices as multiple options** — When feedback contradicts itself, present both as alternatives
- **Per-category reset capability** — Allow clearing stock preferences, or toolpath preferences, or all independently
- **Shop-wide learning pool** — All users contribute to same feedback history; team learns together

### Confidence Adjustment
- **Boost confidence on acceptance** — Each time user picks the suggestion, confidence increases
- **Exponential decay weighting** — Recent feedback counts more; old feedback has less weight over time
- **Require 3+ samples before adjusting** — Don't change confidence until at least 3 feedback events exist for this context
- **Acceptance rate calculation** — Confidence = (# accepted) / (# total) for matching context
- **Explicit feedback is stronger signal** — Thumbs up/down counts 2x weight compared to implicit acceptance/rejection

### Feedback Presentation
- **Source tag: 'user_preference'** — Show `source: user_preference` in suggestion JSON when influenced by learning
- **Feedback history query via MCP + export** — `get_feedback_stats()` operation AND export to CSV/JSON
- **Flag tentative preferences** — Confidence <0.60 from learning shows as 'tentative' or 'limited data'
- **First-time learning notification** — One-time message when pattern kicks in: "I noticed you prefer X for aluminum"
- **Export both JSON and CSV formats** — Support both, user chooses at export time
- **Implicit learning only (no UI buttons)** — Record when user picks differently; no 'save as preference' button
- **Stats granularity:**
  - Per-operation type (stock suggestions: 85%, toolpath: 60%, etc.)
  - Per-material (aluminum: 80%, steel: 65%, etc.)
  - Per-geometry type (pockets: 75%, holes: 95%, etc.)

### Claude's Discretion
- **Geometry hash vs field queries** — Choose whether to hash (material+geometry+dimensions) for fast lookups or query by fields
- **Confidence drop on rejection** — Decide magnitude (small 5-10%, large 20-30%, or proportional to difference)
- **Minimum confidence floor** — Choose floor value (0.20, 0.50, or no floor)
- **Suggestion vs confidence influence** — Choose whether learning changes suggestion itself, confidence only, or both

</decisions>

<specifics>
## Specific Ideas

- "I want it to learn silently in the background and just get better over time"
- "If I override something multiple times, it should pick up on that pattern"
- "Should be able to see why it suggested something if I ask"
- Acceptance rate should be simple and interpretable, not overly statistical

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-learning-system*
*Context gathered: 2026-02-06*
