# Phase 1: Foundation — CAM State Access - Context

**Gathered:** 2026-02-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish basic CAM API access and state querying. Implement `get_cam_state` and `get_tool_library` operations that allow AI agents to query Fusion 360's CAM workspace, setups, operations, and tool library via MCP.

</domain>

<decisions>
## Implementation Decisions

### Response Structure
- Always include units explicitly: `{"value": 10, "unit": "mm"}` — no ambiguity
- Return full tool definitions with all Fusion tool properties (flutes, helix angle, coating, vendor, etc.)
- Include WCS (Work Coordinate System) info per setup — origin and orientation relative to model

### Tool Filtering
- Default scope is document library; optional flag to include cloud library
- Filtering uses exact values with implicit tolerance (e.g., `diameter=10` matches within tolerance)

### Claude's Discretion
- Response hierarchy structure (nested vs flat with references)
- Level of detail for operations (summary vs full parameters)
- Whether to include machine/post-processor details in get_cam_state
- Whether to include timestamps/metadata
- Whether to include error details for failed operations or just status flags
- Which filter options to expose (type, diameter, material, etc.)
- Whether filters are required or all optional

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-foundation-cam-state-access*
*Context gathered: 2026-02-05*
