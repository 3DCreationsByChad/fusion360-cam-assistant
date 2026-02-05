# Phase 3: Stock Suggestions - Context

**Gathered:** 2026-02-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Suggest stock setup based on geometry analysis — calculating dimensions from bounding box, applying offsets, recommending orientation based on feature accessibility, and storing/retrieving user preferences from SQLite. Creating toolpaths and feeds/speeds are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Orientation recommendation logic
- Return best orientation, plus alternatives only when scores are within threshold
- When orientation confidence is low, ask user to choose before returning stock suggestion
- Always include setup sequence (flip instructions) with every stock suggestion, even for single-setup parts

### Preference storage & retrieval
- Preferences keyed by material + geometry type (e.g., "aluminum + pocket-heavy")
- When no matching preference exists, prompt user to establish preference for this combination
- Always show source attribution ('from: user_preference' or 'from: default')
- Full preference profile includes: offsets, preferred orientation, stock shape, machining allowance

### Response structure & confidence
- Include reasoning explaining why orientation/offset was chosen (not full diagnostic)
- Round dimensions to standard stock sizes based on document unit system
- For cylindrical parts, show both round and rectangular stock options with trade-offs

### Claude's Discretion
- Threshold for "close alternatives" (suggested ~10-15% score gap)
- Specific standard stock size tables for metric vs imperial
- How to detect cylindrical/turned parts vs prismatic
- SQLite schema design details

</decisions>

<specifics>
## Specific Ideas

- User wants interactive prompting when preferences don't exist or confidence is low — not silent defaults
- Stock matching to standard sizes is important for real-world shop use
- Source attribution ("from: user_preference") helps user understand and trust suggestions

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-stock-suggestions*
*Context gathered: 2026-02-05*
