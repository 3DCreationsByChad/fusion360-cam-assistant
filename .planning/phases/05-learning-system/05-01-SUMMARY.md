---
phase: 05-learning-system
plan: 01
subsystem: learning
tags: [sqlite, feedback, machine-learning, exponential-decay, confidence-scoring]

# Dependency graph
requires:
  - phase: 03-stock-setup
    provides: "preference_store.py pattern for SQLite operations via MCP bridge"
  - phase: 04-toolpath-strategy
    provides: "strategy_preferences.py pattern for user preference storage"
provides:
  - "feedback_learning module with SQLite storage for feedback events"
  - "Exponential decay recency weighting (W = e^(-lambda*t))"
  - "Confidence adjustment from acceptance rate (3+ samples, 0.20 floor)"
  - "Material family matching with LIKE queries"
  - "Conflict detection for multiple user choice patterns"
affects: [05-02-feedback-handlers, future-learning-enhancements]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Exponential decay time weighting for temporal data"
    - "Confidence blending: base * (1-w) + acceptance * w"
    - "Pure Python modules (recency_weighting, confidence_adjuster) for testability"
    - "Material family matching with LIKE for cross-material learning"

key-files:
  created:
    - "Fusion-360-MCP-Server/feedback_learning/__init__.py"
    - "Fusion-360-MCP-Server/feedback_learning/feedback_store.py"
    - "Fusion-360-MCP-Server/feedback_learning/recency_weighting.py"
    - "Fusion-360-MCP-Server/feedback_learning/confidence_adjuster.py"
    - "Fusion-360-MCP-Server/feedback_learning/context_matcher.py"
  modified: []

key-decisions:
  - "Exponential decay halflife default 30 days (configurable parameter)"
  - "MIN_SAMPLES=3 before adjusting confidence (per CONTEXT.md)"
  - "CONFIDENCE_FLOOR=0.20 prevents death spiral (per RESEARCH.md)"
  - "Explicit feedback 2x weight vs implicit (per CONTEXT.md)"
  - "Full trust at 10+ samples (FULL_TRUST_SAMPLES)"
  - "TENTATIVE_THRESHOLD=0.60 for flagging low-confidence suggestions"
  - "Material LIKE matching for family-based learning (e.g., '6061 aluminum' matches 'aluminum')"

patterns-established:
  - "Pure Python temporal weighting module (stdlib only, no MCP/Fusion dependencies)"
  - "Confidence blending: linear ramp from 0% base at 3 samples to 100% acceptance at 10 samples"
  - "UTC-aware datetime handling (datetime.now(timezone.utc))"
  - "JSON serialization with sort_keys=True for consistent keying"
  - "Separate CREATE INDEX statements (SQLite doesn't support inline INDEX)"

# Metrics
duration: 4min
completed: 2026-02-06
---

# Phase 05 Plan 01: Feedback Learning Foundation Summary

**SQLite feedback storage with exponential decay recency weighting (30-day halflife), confidence blending (3+ samples, 0.20 floor), and material family matching**

## Performance

- **Duration:** 4 minutes
- **Started:** 2026-02-06T20:07:03Z
- **Completed:** 2026-02-06T20:11:00Z
- **Tasks:** 2
- **Files created:** 5

## Accomplishments

- **feedback_store.py**: SQLite schema with cam_feedback_history table, record_feedback, get_feedback_statistics (overall + 3 breakdowns), export_feedback_history (CSV/JSON), clear_feedback_history (per-category reset)
- **recency_weighting.py**: Pure Python exponential decay (W = e^(-lambda*t), lambda = ln(2)/halflife_days), 2x weight multiplier for explicit feedback
- **confidence_adjuster.py**: Confidence blending with MIN_SAMPLES=3, CONFIDENCE_FLOOR=0.20, TENTATIVE_THRESHOLD=0.60, linear ramp to FULL_TRUST_SAMPLES=10
- **context_matcher.py**: Material family matching with LIKE queries, conflict detection for multiple user choices, JSON parsing for context/suggestion/user_choice
- **__init__.py**: All public APIs exported with relative imports for Fusion add-in package context

## Task Commits

Each task was committed atomically:

1. **Task 1: Create feedback_store.py with SQLite schema and operations** - `3d6a525` (feat)
2. **Task 2: Create recency_weighting, confidence_adjuster, context_matcher, and __init__.py** - `f98316e` (feat)

## Files Created/Modified

**Created:**
- `Fusion-360-MCP-Server/feedback_learning/__init__.py` - Module exports for feedback_learning package
- `Fusion-360-MCP-Server/feedback_learning/feedback_store.py` - SQLite storage and retrieval (table, indexes, CRUD, statistics, export, clear)
- `Fusion-360-MCP-Server/feedback_learning/recency_weighting.py` - Exponential decay time weighting (pure Python, stdlib only)
- `Fusion-360-MCP-Server/feedback_learning/confidence_adjuster.py` - Acceptance rate confidence blending (pure Python)
- `Fusion-360-MCP-Server/feedback_learning/context_matcher.py` - Field-based querying with material LIKE matching and conflict detection

**Modified:**
- None

## Decisions Made

1. **Exponential decay halflife: 30 days default**
   - Rationale: Balances recent feedback importance with historical stability. Configurable parameter allows tuning.

2. **MIN_SAMPLES = 3 before adjusting confidence**
   - Rationale: Per CONTEXT.md decision. Prevents noisy adjustments from 1-2 samples.

3. **CONFIDENCE_FLOOR = 0.20**
   - Rationale: Per RESEARCH.md open question #3. Prevents death spiral where low confidence → user rejects → lower confidence.

4. **Explicit feedback 2x weight multiplier**
   - Rationale: Per CONTEXT.md decision. Explicit good/bad is higher signal than implicit accept/reject.

5. **FULL_TRUST_SAMPLES = 10**
   - Rationale: At 10+ samples, acceptance rate fully replaces base confidence. Linear blend ramp from 3 to 10 samples.

6. **TENTATIVE_THRESHOLD = 0.60**
   - Rationale: Per CONTEXT.md. Flag suggestions below 0.60 confidence as "tentative" for user awareness.

7. **Material family matching with LIKE**
   - Rationale: Enables cross-material learning (e.g., "6061 aluminum" feedback applies to "aluminum" queries). Increases sample size for rare materials.

8. **Pure Python for recency_weighting and confidence_adjuster**
   - Rationale: No MCP or Fusion API dependencies → easily unit testable, reusable, portable.

9. **JSON serialization with sort_keys=True**
   - Rationale: Ensures consistent serialization for comparison (user_choice grouping, conflict detection).

10. **Separate CREATE INDEX statements**
    - Rationale: SQLite doesn't support inline INDEX in CREATE TABLE. Must use separate CREATE INDEX IF NOT EXISTS.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for Plan 02 (Feedback MCP Handlers):**
- feedback_learning module complete with all required functions
- SQLite schema defined and initialization function ready
- Recency weighting and confidence adjustment logic tested via implementation review
- Material family matching and conflict detection ready for integration

**Integration notes:**
- Plan 02 will add record_user_choice MCP operation calling record_feedback()
- Existing MCP operations (stock_setup, toolpath_strategy) will call get_matching_feedback() + adjust_confidence_from_feedback()
- initialize_feedback_schema() must be called on add-in startup (likely in mcp_integration.py)

**No blockers or concerns.**

---
*Phase: 05-learning-system*
*Completed: 2026-02-06*
