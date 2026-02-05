# Phase 2: Geometry Analysis - Context

**Gathered:** 2026-02-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Analyze part geometry to extract CAM-relevant information: bounding box, volume, surface area, feature detection (pockets, holes, slots), material detection, minimum tool radius requirements, and orientation suggestions. This is an analysis/read operation — no modifications to the model.

</domain>

<decisions>
## Implementation Decisions

### Feature Detection Criteria
- Holes defined as any cylindrical through-feature (not limited to axis-aligned)
- Slot vs pocket distinction: Claude's discretion to define heuristics
- Blind holes: Claude's discretion whether to classify separately or group with pockets
- Configurable size threshold for feature detection (default provided, overridable per-analysis)

### Output Structure
- Features grouped by machining priority (not by type)
- Rich metadata per feature: dimensions, depth, position, Fusion face/edge IDs, surface area, volume removed, bounding box
- Minimum tool radius: both global minimum AND per-feature values
- Bounding box scope: Claude's discretion on part-level vs per-feature

### Confidence & Uncertainty
- Every feature includes a confidence score (0-1) for its classification
- Ambiguous features: provide best-guess classification + `needs_review: true` flag
- Every feature includes reasoning explaining why it was classified that way
- Analysis summary: Claude's discretion on what quality metrics to include

### Orientation Suggestions
- Primary optimization goal: minimize setups/flips
- Return all viable orientations, ranked
- Each orientation includes recommended setup/op sequence (machine this face, flip, then that)
- Explicitly flag features that are unreachable in any 3-axis orientation (undercuts, internal cavities)

### Claude's Discretion
- Exact heuristics for slot vs pocket classification
- Blind hole handling (separate type vs pocket)
- Bounding box granularity (part-level vs per-feature)
- Analysis summary content

</decisions>

<specifics>
## Specific Ideas

- Features should be actionable for CAM — include Fusion geometry IDs for programmatic selection
- Orientation suggestions should help user plan their workholding before they even open CAM workspace
- Unreachable features flagged early saves time — user knows what needs special tooling or 4th axis

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-geometry-analysis*
*Context gathered: 2026-02-05*
