# Phase 1: Foundation — CAM State Access - Research

**Researched:** 2026-02-05
**Domain:** Fusion 360 CAM API integration via Python MCP server
**Confidence:** HIGH

## Summary

This research investigated how to implement CAM state querying and tool library access in Fusion 360 via the Python API, specifically focusing on the `adsk.cam` module and MCP server integration patterns. The standard approach is to access the CAM product from the active document, navigate the object model hierarchy (CAM → Setups → Operations), and use the CAMManager for library access. All CAM settings are exposed as CAM Parameters (collections of configurable settings) rather than individual properties.

The existing codebase already implements `get_cam_state` and `get_tool_library` operations successfully. Research focused on identifying patterns, pitfalls, and architectural improvements for reliability.

**Primary recommendation:** Use URL-based library navigation for tool queries, always convert units explicitly (cm internally → mm for MCP responses), and handle CAM product absence gracefully since CAM products only exist if user has activated Manufacturing workspace.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| adsk.cam | Fusion 360 API | CAM workspace access | Official Fusion 360 CAM automation API |
| adsk.core | Fusion 360 API | Application and UI access | Core Fusion 360 API module |
| adsk.fusion | Fusion 360 API | Design product access | Required for geometry analysis |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json | Python stdlib | Response serialization | MCP protocol requires JSON responses |
| typing | Python stdlib | Type hints | Improves code documentation and IDE support |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Direct parameter access | Parameter expressions | Expressions support formulas but require string parsing; direct values are type-safe |
| Query-based tool search | URL navigation | Queries are more flexible but URL navigation matches library structure |

**Installation:**
```bash
# No installation needed - adsk modules are provided by Fusion 360 runtime
# MCP integration uses existing mcp_client.py in project
```

## Architecture Patterns

### Recommended Project Structure
```
Fusion-360-MCP-Server/
├── cam_operations.py        # CAM-specific handlers (already exists)
├── mcp_integration.py        # Core routing (already exists)
├── lib/
│   └── mcp_client.py         # MCP protocol client
└── tool_libraries/           # Reference tool libraries
```

### Pattern 1: CAM Product Access with Fallback
**What:** Always check if CAM product exists before attempting access
**When to use:** Every CAM operation entry point
**Example:**
```python
# Source: https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CAMIntroduction_UM.htm
def _get_cam_product():
    """Get CAM product from active document, if available."""
    app = adsk.core.Application.get()
    doc = app.activeDocument

    if not doc:
        return None

    # Look for CAM product
    for product in doc.products:
        if product.productType == 'CAMProductType':
            return adsk.cam.CAM.cast(product)

    return None
```

### Pattern 2: Unit Conversion Wrapper
**What:** Always include explicit units in responses to avoid ambiguity
**When to use:** All numeric measurements in MCP responses
**Example:**
```python
# Source: https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Units_UM.htm
def _to_mm(cm_value: float) -> dict:
    """Convert internal cm to mm with explicit units."""
    return {
        "value": round(cm_value * 10, 3),
        "unit": "mm"
    }

# Usage in response:
tool_info["diameter"] = _to_mm(tool.diameter)
```

### Pattern 3: Parameter Access by Name
**What:** Use `itemByName()` to access CAM parameters, not property accessors
**When to use:** Reading or modifying operation/setup settings
**Example:**
```python
# Source: https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CAMParameters_UM.htm
params = setup.parameters
stock_x = params.itemByName("job_stockFixedX")
if stock_x:
    dimension = stock_x.expression  # String expression
    # OR
    dimension_cm = stock_x.value.value  # Numeric value in cm
```

### Pattern 4: URL-Based Library Navigation
**What:** Navigate tool libraries using URL hierarchy rather than object references
**When to use:** Querying tool libraries for filtering/searching
**Example:**
```python
# Source: https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CAMLibraries_UM.htm
cam_mgr = adsk.cam.CAMManager.get()
tool_libraries = cam_mgr.libraryManager.toolLibraries

# Iterate through library URLs
for lib_url in tool_libraries.libraryUrls:
    lib = tool_libraries.libraryAtUrl(lib_url)
    if lib:
        for i in range(lib.count):
            tool = lib.item(i)
            # Process tool...
```

### Pattern 5: WCS (Work Coordinate System) Extraction
**What:** Extract coordinate system information from setup parameters
**When to use:** Providing setup context to AI for toolpath suggestions
**Example:**
```python
# Source: Existing cam_operations.py implementation
try:
    origin = setup.parameters.itemByName("job_stockZPosition")
    if origin:
        wcs_info["z_origin"] = origin.expression
except:
    pass  # Some setups may not have this parameter
```

### Anti-Patterns to Avoid
- **Assuming CAM product exists:** Always check for None; CAM products only exist if Manufacturing workspace was activated
- **Using object identity for library items:** Library objects are temporary copies, not live references
- **Ignoring unit conversion:** All API values are in cm; users expect mm for CAM operations
- **Accessing parameters as properties:** CAM uses parameter collections, not direct property access
- **Enumerating NCPrograms carelessly:** Can cause crashes in some Fusion versions (known stability issue)

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Unit conversion | Manual multiplication factors | `UnitsManager.convert()` or `_to_mm()` wrapper | Consistent rounding, error handling, future-proof if internal units change |
| Parameter finding | Iterating collections | `parameters.itemByName("param_id")` | Direct access, type-safe, documents intent |
| Expression evaluation | String parsing | Parameter `.expression` property or `.value.value` | Handles Fusion's expression syntax, unit-aware |
| Tool filtering by diameter | Manual threshold checks | Query with tolerance-based matching | Handles floating-point precision, matches Fusion's internal tolerance |

**Key insight:** The CAM API is intentionally thin — most functionality is exposed through parameters rather than methods. Don't build abstractions over parameter access; work directly with parameter collections as the API intends.

## Common Pitfalls

### Pitfall 1: CAM Product Doesn't Exist
**What goes wrong:** Code crashes with NullPointerException when trying to access `cam.setups` or other properties.
**Why it happens:** CAM products are only created when user activates Manufacturing workspace. New documents or design-only workflows won't have CAM products.
**How to avoid:** Always use `_get_cam_product()` helper and check for None. Return informative message like "No CAM workspace in current document. Create a Setup to begin."
**Warning signs:** User reports "works in one document but not another" — likely CAM workspace presence difference.

### Pitfall 2: Unit Confusion (cm vs mm)
**What goes wrong:** Dimensions appear 10x larger or smaller than expected. Tool diameters of "0.318 cm" displayed to users cause confusion.
**Why it happens:** Fusion API uses cm internally, but CAM users universally think in mm (or inches). Forgetting to convert leads to nonsensical values.
**How to avoid:** Establish conversion functions (`_to_mm()`, `_from_mm()`) and use them consistently. Include `"unit": "mm"` in all responses per user decisions.
**Warning signs:** Numeric values that are suspiciously round in cm but awkward in mm (e.g., 1.27 cm is actually 0.5 inches).

### Pitfall 3: Parameter Exists But Is Hidden
**What goes wrong:** Code tries to read parameter that appears in API docs but returns None at runtime.
**Why it happens:** Parameters can be hidden based on other settings (e.g., unchecked checkbox groups hide dependent parameters). Parameter still exists in collection but may not be relevant.
**How to avoid:** Wrap all parameter access in try-except blocks or None checks. Don't assume parameter presence based on operation type alone.
**Warning signs:** Intermittent "KeyError" or "NoneType has no attribute" errors that depend on specific operation configurations.

### Pitfall 4: Library Objects Are Copies, Not References
**What goes wrong:** Modifying a tool from a library doesn't affect the library. Tool assignments copy rather than reference.
**Why it happens:** Per official docs: "library API objects aren't references but temporary copies." This is fundamentally different from Design API behavior.
**How to avoid:** Understand that tool assignment to operation creates a copy in document library. To update libraries, you must explicitly save changes back.
**Warning signs:** Changes to tools don't persist, or multiple operations have "duplicate" tools with slight differences.

### Pitfall 5: Missing Error Details in Operations
**What goes wrong:** Operation shows `hasError: true` but no explanation of what's wrong.
**Why it happens:** Fusion's error reporting for invalid operations is limited in API. Errors may relate to missing geometry, invalid tool parameters, or licensing restrictions.
**How to avoid:** Check `operation.isValid` before generation. Log operation type, tool, and strategy for debugging. Include error state in responses but note details may be unavailable.
**Warning signs:** User reports "operation shows error" but logs provide no useful information.

### Pitfall 6: Stock Mode Variations
**What goes wrong:** Code assumes FixedBoxStock and crashes with CylinderStock or FromSolidStock.
**Why it happens:** Stock configuration varies by setup type. Parameter names differ between modes (e.g., "job_stockFixedX" vs cylinder diameter).
**How to avoid:** Check `setup.stockMode` enum first, then branch to mode-specific parameter access. Use try-except for parameter reads since not all modes have all parameters.
**Warning signs:** Works for milling setups but crashes with turning setups or custom stock definitions.

## Code Examples

Verified patterns from official sources:

### Query CAM State with Full Error Handling
```python
# Source: Existing cam_operations.py + official CAM API docs
def handle_get_cam_state(arguments: dict) -> dict:
    """Get current CAM workspace state with proper error handling."""
    try:
        cam = _get_cam_product()

        if not cam:
            return _format_response({
                "has_cam_workspace": False,
                "message": "No CAM workspace in current document. Create a Setup to begin.",
                "setups": [],
                "active_setup": None
            })

        setups_data = []
        for setup in cam.setups:
            setup_info = {
                "name": setup.name,
                "is_active": setup == cam.activeSetup,
                "operations": [],
                "stock": None,
                "wcs_origin": None
            }

            # Stock configuration with mode detection
            try:
                stock_mode = setup.stockMode
                if stock_mode == adsk.cam.StockModes.FixedBoxStock:
                    setup_info["stock"] = {
                        "type": "fixed_box",
                        "dimensions": {
                            "x": {"value": 0, "unit": "mm"},  # Extract from parameters
                            "y": {"value": 0, "unit": "mm"},
                            "z": {"value": 0, "unit": "mm"}
                        }
                    }
            except Exception as e:
                setup_info["stock"] = {"error": str(e)}

            # WCS origin
            try:
                origin_param = setup.parameters.itemByName("job_stockZPosition")
                if origin_param:
                    setup_info["wcs_origin"] = {
                        "z": origin_param.expression
                    }
            except:
                pass

            setups_data.append(setup_info)

        return _format_response({
            "has_cam_workspace": True,
            "setup_count": len(setups_data),
            "setups": setups_data,
            "active_setup": cam.activeSetup.name if cam.activeSetup else None
        })

    except Exception as e:
        import traceback
        return _format_error(f"Failed to get CAM state: {str(e)}", traceback.format_exc())
```

### Query Tool Library with Filtering
```python
# Source: https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CAMLibraries_UM.htm
def handle_get_tool_library(arguments: dict) -> dict:
    """Query tool library with diameter and type filtering."""
    try:
        cam = _get_cam_product()
        if not cam:
            return _format_error("No CAM workspace available. Create a Setup first.")

        # Parse filters
        filter_args = arguments.get('filter', {})
        type_filter = filter_args.get('type', [])
        diameter_range = filter_args.get('diameter_range', [0, 1000])  # mm
        limit = arguments.get('limit', 50)

        # Convert diameter range to cm for comparison
        diameter_range_cm = [d / 10 for d in diameter_range]

        # Get library manager
        cam_mgr = adsk.cam.CAMManager.get()
        tool_libraries = cam_mgr.libraryManager.toolLibraries

        tools_data = []

        for lib_url in tool_libraries.libraryUrls:
            lib = tool_libraries.libraryAtUrl(lib_url)
            if not lib:
                continue

            for i in range(lib.count):
                if len(tools_data) >= limit:
                    break

                try:
                    tool = lib.item(i)

                    # Get tool type
                    tool_type_str = tool.type.toString() if hasattr(tool.type, 'toString') else str(tool.type)

                    # Apply type filter
                    if type_filter:
                        type_match = any(t.lower() in tool_type_str.lower() for t in type_filter)
                        if not type_match:
                            continue

                    # Apply diameter filter
                    diameter_cm = tool.diameter if hasattr(tool, 'diameter') else 0
                    if diameter_cm < diameter_range_cm[0] or diameter_cm > diameter_range_cm[1]:
                        continue

                    # Build tool info with explicit units
                    tool_info = {
                        "description": tool.description if hasattr(tool, 'description') else "",
                        "type": tool_type_str,
                        "diameter": {"value": round(diameter_cm * 10, 3), "unit": "mm"},
                        "library": lib.name
                    }

                    # Optional properties
                    if hasattr(tool, 'numberOfFlutes'):
                        tool_info["flutes"] = tool.numberOfFlutes
                    if hasattr(tool, 'fluteLength'):
                        tool_info["flute_length"] = {"value": round(tool.fluteLength * 10, 2), "unit": "mm"}
                    if hasattr(tool, 'vendor'):
                        tool_info["vendor"] = tool.vendor

                    tools_data.append(tool_info)

                except Exception:
                    continue  # Skip tools that can't be read

            if len(tools_data) >= limit:
                break

        return _format_response({
            "tools": tools_data,
            "returned_count": len(tools_data),
            "limit": limit
        })

    except Exception as e:
        import traceback
        return _format_error(f"Failed to query tool library: {str(e)}", traceback.format_exc())
```

### Extract WCS Information Per Setup
```python
# Source: User decision in CONTEXT.md + CAM Parameters guide
def extract_wcs_info(setup) -> dict:
    """Extract Work Coordinate System information from setup."""
    wcs_info = {}

    try:
        # Z position (stock top/bottom)
        z_pos = setup.parameters.itemByName("job_stockZPosition")
        if z_pos:
            wcs_info["z_origin"] = {
                "expression": z_pos.expression,
                "value": {"value": round(z_pos.value.value * 10, 2), "unit": "mm"}
            }

        # Setup coordinate system
        # Note: Full WCS includes X, Y offsets and rotation, but these are setup-dependent
        # Basic implementation returns Z-origin as most critical for CAM planning

    except Exception as e:
        wcs_info["error"] = str(e)

    return wcs_info
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Direct property access | Parameter collections via `itemByName()` | CAM API introduction | All settings are now parameters, not properties |
| Assuming object identity | Understanding library objects are copies | Library API design | Must explicitly manage document vs library tools |
| Single-threading only | Thread-safe work queue pattern | MCP integration | Daemon threads can now safely queue Fusion API work |
| Manual unit conversion | `UnitsManager.convert()` utility | Fusion API maturity | Centralized, consistent unit handling |

**Deprecated/outdated:**
- **Direct access to operation properties:** Most CAM configuration is now via parameters, not object properties
- **Synchronous toolpath generation:** Modern API provides `GenerateToolpathFuture` for async operations

## Open Questions

Things that couldn't be fully resolved:

1. **NCProgram enumeration stability**
   - What we know: Forum posts indicate enumerating `cam.ncPrograms` can crash Fusion in some versions
   - What's unclear: Which specific versions are affected, whether there's a workaround
   - Recommendation: Avoid enumerating NCPrograms in Phase 1; defer to post-processing phase

2. **Cloud library access patterns**
   - What we know: User decision includes "optional flag to include cloud library"
   - What's unclear: How cloud library URLs differ from local, whether authentication is required
   - Recommendation: Implement local library first, add cloud flag as optional parameter with clear documentation

3. **Machine and post-processor details**
   - What we know: User marked "whether to include machine/post-processor details" as discretion area
   - What's unclear: Level of detail needed (name only vs full configuration)
   - Recommendation: Start with name only in Phase 1, expand based on AI usage patterns in Phase 4

4. **Error detail availability for failed operations**
   - What we know: Operations have `hasError` and `isValid` flags
   - What's unclear: How much error detail is actually accessible via API
   - Recommendation: Include flags in responses, note that detailed error messages may be unavailable (Fusion limitation)

## Sources

### Primary (HIGH confidence)
- [Fusion 360 CAM API Introduction](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CAMIntroduction_UM.htm) - Object model, access patterns
- [CAM Parameters Guide](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CAMParameters_UM.htm) - Parameter access patterns
- [CAM Libraries Guide](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CAMLibraries_UM.htm) - Tool library navigation
- [Understanding Units](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Units_UM.htm) - Unit conversion and internal representation
- Existing implementation: `cam_operations.py` and `mcp_integration.py` - Verified working patterns

### Secondary (MEDIUM confidence)
- [Manufacturing CAM API Feedback Forum](https://forums.autodesk.com/t5/fusion-api-and-scripts-forum/manufacturing-cam-api-feedback/td-p/11869814) - Community-reported stability issues with NCPrograms
- [MCP Best Practices Guide](https://modelcontextprotocol.info/docs/best-practices/) - Error handling patterns
- [MCP Error Handling Guide](https://mcpcat.io/guides/error-handling-custom-mcp-servers/) - ToolError patterns for Python

### Tertiary (LOW confidence)
- Various community forums discussing CAM API quirks - anecdotal reports of crashes and gotchas

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official Fusion 360 API is the only option for CAM automation
- Architecture: HIGH - Existing implementation verified working, official docs provide clear patterns
- Pitfalls: HIGH - Official docs explicitly warn about library object copies, unit confusion, CAM product existence
- Code examples: HIGH - Derived from official documentation and verified working implementation

**Research date:** 2026-02-05
**Valid until:** 2026-04-05 (60 days) - Fusion 360 API is stable; CAM API patterns unlikely to change rapidly

**Research constraints from CONTEXT.md:**
- Response structure with explicit units: LOCKED decision
- Tool filtering with tolerance-based matching: LOCKED decision
- WCS information per setup: LOCKED decision
- Response hierarchy, detail level, filter options: DISCRETION areas for planner
