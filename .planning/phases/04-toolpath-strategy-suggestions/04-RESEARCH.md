# Phase 4: Toolpath Strategy Suggestions - Research

**Researched:** 2026-02-05
**Domain:** CNC machining strategy recommendation, CAM operation selection, feeds/speeds calculation
**Confidence:** MEDIUM-HIGH

## Summary

This research investigated how to build a toolpath strategy recommendation system for Fusion 360 CAM. The system must map detected geometry features (holes, pockets, slots from Phase 2) to recommended CAM operations (drilling, adaptive clearing, pocketing, contouring), select appropriate tools from the library, and calculate basic feeds/speeds based on material properties.

The CNC machining domain has well-established heuristics for operation selection based on feature types and material properties. Adaptive clearing is preferred for hard materials requiring heat management (aluminum, plastics), while pocket clearing is faster for soft materials (wood, MDF). Tool selection follows the "largest tool that fits" principle. Feeds and speeds are calculated using standard formulas: RPM from SFM (surface feet per minute) values, and feed rate from chip load × flutes × RPM.

Fusion 360's CAM API (`adsk.cam`) provides programmatic operation creation through a parameter-based system. Operations are created via `operations.createInput(strategy_id)`, configured through named parameters accessed via `itemByName()`, and then added to a setup. The API uses centimeters internally but parameters accept expressions in document units or direct float values.

**Primary recommendation:** Build a simple rule-based engine using Python dictionaries and functions rather than a heavyweight rules engine library. The domain has ~10-15 core rules, making a custom implementation more maintainable than external dependencies.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| adsk.cam | Fusion 360 API | CAM operation creation and parameter configuration | Official Fusion 360 Python API for programmatic CAM |
| SQLite3 | Python stdlib | Strategy preference storage | Already used in Phase 3 for preferences, no new dependencies |
| json | Python stdlib | Tool library parsing, parameter serialization | Tool.toJson() returns JSON strings per Phase 1 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| None required | - | Rules engine external library | NOT RECOMMENDED - simple dict-based rules suffice |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom rule functions | python-simple-rules-engine, durable-rules | External dependency for ~15 rules is overkill; harder to debug CAM-specific logic |
| SQLite | JSON file | SQLite already in use for preferences; provides atomic updates and query flexibility |

**Installation:**
```bash
# No new dependencies required - uses Python stdlib + existing Fusion 360 API
```

## Architecture Patterns

### Recommended Project Structure
```
Fusion-360-MCP-Server/
├── toolpath_strategy/
│   ├── __init__.py              # Module exports
│   ├── operation_mapper.py      # Feature → operation type mapping
│   ├── tool_selector.py         # Tool selection logic (largest that fits)
│   ├── feeds_speeds.py          # RPM and feed rate calculation
│   ├── material_library.py      # SFM values for common materials
│   └── preference_store.py      # Strategy preference storage (extends existing)
├── cam_operations.py            # Add handle_suggest_toolpath_strategy
└── stock_suggestions/preference_store.py  # Extend with cam_strategy_preferences table
```

### Pattern 1: Rule-Based Feature-to-Operation Mapping
**What:** Map detected feature types to recommended CAM operation types using Python dictionaries and conditional logic
**When to use:** For deterministic mappings with clear heuristics (e.g., hole → drilling, deep pocket → adaptive clearing)
**Example:**
```python
# Source: Industry best practices + Fusion 360 CAM workflow patterns
# https://www.camaster.com/understanding-cnc-toolpath-strategies/

OPERATION_RULES = {
    "hole": {
        "primary": "drilling",
        "conditions": [
            {"if": "diameter < 12.0", "operation": "drilling"},
            {"if": "diameter >= 12.0", "operation": "boring_or_helical"}
        ]
    },
    "pocket": {
        "primary": "adaptive_clearing",
        "conditions": [
            {"if": "depth > 10.0 AND material_hardness > 'soft'", "operation": "adaptive_clearing"},
            {"if": "depth <= 10.0 OR material_hardness == 'soft'", "operation": "2d_pocket"}
        ]
    },
    "slot": {
        "primary": "slot_milling",
        "conditions": [
            {"if": "width <= tool_diameter", "operation": "slot_milling"},
            {"if": "width > tool_diameter", "operation": "adaptive_clearing"}
        ]
    }
}

def map_feature_to_operation(feature: dict, material: str) -> dict:
    """Map feature to recommended operation type."""
    feature_type = feature.get("type")
    rule = OPERATION_RULES.get(feature_type, {})

    # Evaluate conditions (simplified - actual impl would parse conditions)
    for condition in rule.get("conditions", []):
        if evaluate_condition(condition["if"], feature, material):
            return {
                "operation_type": condition["operation"],
                "confidence": 0.9,
                "reasoning": f"Feature type '{feature_type}' matches rule: {condition['if']}"
            }

    # Fallback to primary
    return {
        "operation_type": rule.get("primary", "2d_contour"),
        "confidence": 0.7,
        "reasoning": f"Default operation for {feature_type}"
    }
```

### Pattern 2: Largest Tool That Fits Selection
**What:** Select the largest tool from the library that fits within feature constraints (internal corners, minimum widths)
**When to use:** For any milling operation requiring tool selection
**Example:**
```python
# Source: CNC tool selection best practices
# https://www.cnccookbook.com/cnc-stepover/

def select_best_tool(feature: dict, available_tools: list, tool_type_filter: str = None) -> dict:
    """
    Select largest tool that fits the feature geometry.

    Applies 80% rule for internal corners (from Phase 2 decision).
    """
    # Get minimum radius from feature (if pocket/slot)
    min_radius = feature.get("min_corner_radius", {}).get("value", float('inf'))

    # Apply 80% rule: tool radius should be 80% of corner radius
    max_tool_radius = min_radius * 0.8 if min_radius != float('inf') else float('inf')

    # Filter tools by type if specified
    candidate_tools = available_tools
    if tool_type_filter:
        candidate_tools = [t for t in available_tools if tool_type_filter in t.get("type", "").lower()]

    # Filter by size constraint
    fitting_tools = [
        t for t in candidate_tools
        if t.get("diameter", {}).get("value", 0) / 2 <= max_tool_radius
    ]

    if not fitting_tools:
        return {"error": "No tools fit the feature constraints"}

    # Select largest (sort by diameter descending)
    largest_tool = max(fitting_tools, key=lambda t: t.get("diameter", {}).get("value", 0))

    return {
        "tool": largest_tool,
        "reasoning": f"Largest tool that fits (max radius: {max_tool_radius:.2f}mm)",
        "stepover_roughing": largest_tool["diameter"]["value"] * 0.5,  # 50% for roughing
        "stepover_finishing": largest_tool["diameter"]["value"] * 0.15  # 15% for finishing
    }
```

### Pattern 3: Feeds/Speeds Calculation
**What:** Calculate RPM and feed rate from material SFM and tool geometry
**When to use:** For all toolpath suggestions requiring cutting parameters
**Example:**
```python
# Source: Standard machining formulas
# https://www.harveyperformance.com/in-the-loupe/speeds-and-feeds-101/
# https://www.cnclathing.com/milling-speed-and-feed-calculator

MATERIAL_SFM = {
    # HSS values - multiply by 3 for carbide
    "aluminum": 400,
    "mild_steel": 100,
    "stainless_steel": 40,
    "brass": 300,
    "plastic": 500,
    "wood": 600
}

CHIP_LOAD_PER_FLUTE = {
    # In inches - typical starting values for carbide endmills
    "aluminum": 0.001,
    "mild_steel": 0.0005,
    "stainless_steel": 0.0003,
    "brass": 0.0008,
    "plastic": 0.001,
    "wood": 0.002
}

def calculate_feeds_speeds(material: str, tool: dict, is_carbide: bool = True, operation_type: str = "roughing") -> dict:
    """
    Calculate RPM and feed rate based on material and tool.

    Formulas:
    - RPM = (SFM × 3.82) / tool_diameter_inches
    - Feed Rate = RPM × flutes × chip_load
    """
    # Get material properties
    material_key = material.lower().replace(" ", "_")
    sfm = MATERIAL_SFM.get(material_key, 100)  # Default conservative SFM

    # Carbide can run 3x faster than HSS
    if is_carbide:
        sfm *= 3

    # Get tool properties
    diameter_mm = tool.get("diameter", {}).get("value", 6.0)
    diameter_inches = diameter_mm / 25.4
    flutes = tool.get("flutes", 4)

    # Calculate RPM: SFM × 3.82 / diameter
    rpm = (sfm * 3.82) / diameter_inches

    # Get chip load
    chip_load = CHIP_LOAD_PER_FLUTE.get(material_key, 0.0005)

    # Reduce chip load for finishing
    if operation_type == "finishing":
        chip_load *= 0.5

    # Calculate feed rate (inches per minute)
    feed_ipm = rpm * flutes * chip_load
    feed_mmpm = feed_ipm * 25.4

    return {
        "rpm": {"value": round(rpm), "unit": "rpm"},
        "feed_rate": {"value": round(feed_mmpm), "unit": "mm/min"},
        "sfm": {"value": sfm, "unit": "ft/min"},
        "chip_load": {"value": round(chip_load, 4), "unit": "in/tooth"},
        "calculation_basis": f"{material_key} with {'carbide' if is_carbide else 'HSS'} {diameter_mm}mm {flutes}-flute"
    }
```

### Pattern 4: Fusion 360 CAM API Operation Creation
**What:** Create CAM operations programmatically using Fusion's parameter-based API
**When to use:** When implementing operation suggestions that the user can accept
**Example:**
```python
# Source: Fusion 360 CAM API documentation
# https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CAMIntroduction_UM.htm

def create_adaptive_clearing_operation(setup, tool, feature_faces, feeds_speeds: dict):
    """
    Create an adaptive clearing operation programmatically.

    Note: This is illustrative - actual implementation would be in a later task.
    Phase 4 focuses on SUGGESTIONS, not programmatic creation.
    """
    # Get compatible strategies for this setup
    strategies = setup.operations.compatibleStrategies
    adaptive_strategy = None
    for strategy in strategies:
        if "adaptive" in strategy.title.lower():
            adaptive_strategy = strategy
            break

    if not adaptive_strategy:
        return {"error": "Adaptive clearing strategy not available"}

    # Create operation input
    op_input = setup.operations.createInput(adaptive_strategy)

    # Configure parameters (API uses parameter names, not direct properties)
    params = op_input.parameters

    # Set tool
    tool_param = params.itemByName("tool_id")
    if tool_param:
        tool_param.value.value = tool["id"]

    # Set feeds/speeds (API uses cm internally, but accepts expressions)
    rpm_param = params.itemByName("tool_spindleSpeed")
    if rpm_param:
        rpm_param.expression = str(feeds_speeds["rpm"]["value"])

    feed_param = params.itemByName("tool_feedCutting")
    if feed_param:
        feed_param.expression = f"{feeds_speeds['feed_rate']['value']} mm/min"

    # Set geometry selection (faces to machine)
    geometry_param = params.itemByName("pocket_selection")
    if geometry_param:
        # geometry_param.value would be set with face selection
        pass

    # Add operation to setup
    operation = setup.operations.add(op_input)

    return {"operation": operation, "name": operation.name}
```

### Anti-Patterns to Avoid
- **Hardcoding SFM/chip load values in operation mapper:** Separate material properties into a dedicated library for easy updates
- **Creating operations immediately without user confirmation:** Phase 4 provides SUGGESTIONS; actual creation is Phase 5+
- **Ignoring tool library availability:** Always check if recommended tool exists before suggesting it
- **Using Python rules engine libraries for simple mappings:** Adds dependency overhead for ~15 rules; dict-based approach is clearer
- **Assuming all materials are in the library:** Provide sensible defaults for unknown materials

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Material property database | Custom material SFM tables from scratch | Start with standard values + allow user overrides via preferences | Standard values exist; edge cases need customization anyway |
| Chip load calculation | Complex physics-based models | Standard formula with manufacturer-recommended starting values | Industry uses empirical values, not first-principles calculations |
| Tool wear prediction | ML model for tool life | Simple heuristic warnings (e.g., "aggressive for this material") | Insufficient data for ML; heuristics provide value faster |
| Operation parameter validation | Custom validation for every parameter | Fusion 360 API's built-in parameter validation | API already validates parameter ranges and types |

**Key insight:** CNC machining has well-established empirical formulas and heuristics. The value is in encoding domain knowledge, not reinventing calculation methods. Start with conservative standard values and allow preference-based refinement.

## Common Pitfalls

### Pitfall 1: SFM Values Don't Account for Tool Material
**What goes wrong:** Using HSS (High-Speed Steel) SFM values with carbide tools results in extremely slow, inefficient machining
**Why it happens:** Material SFM charts often list HSS values by default; carbide can run 3x faster
**How to avoid:** Always identify tool material (HSS vs carbide) and apply the 3x multiplier for carbide
**Warning signs:** Calculated RPM is unusually low (e.g., <2000 for a 6mm endmill in aluminum)

### Pitfall 2: Confusing Stepover with Stepdown
**What goes wrong:** Applying stepover percentages to depth-of-cut calculations or vice versa
**Why it happens:** Both are "step" parameters but control different toolpath dimensions
**How to avoid:**
- Stepover = lateral distance between adjacent passes (XY plane) — typically 40-50% for roughing, 10-20% for finishing
- Stepdown = axial depth per pass (Z direction) — typically 0.5-1.5× tool diameter for roughing
**Warning signs:** Toolpath preview shows unexpectedly shallow or narrow cutting patterns

### Pitfall 3: Recommending Tools That Don't Fit Internal Corners
**What goes wrong:** Suggesting a tool larger than internal corner radii, requiring manual corner cleanup
**Why it happens:** Forgetting to check minimum feature radius or not applying the 80% safety margin
**How to avoid:** Always extract min_corner_radius from pocket/slot features and apply 80% rule (tool radius ≤ 0.8 × corner radius)
**Warning signs:** User asks "why can't I use a larger tool?" or toolpath simulation shows uncut material in corners

### Pitfall 4: Adaptive Clearing for Shallow Features
**What goes wrong:** Recommending adaptive clearing for features <5mm deep wastes time due to longer toolpath
**Why it happens:** Blindly applying "adaptive is better" rule without depth check
**How to avoid:** Use depth threshold: adaptive clearing for depth >10mm, 2D pocket for depth <10mm (per Phase 2 decision)
**Warning signs:** Estimated machining time is unusually high for simple shallow pockets

### Pitfall 5: Ignoring Flute Length Constraints
**What goes wrong:** Suggesting deep pocket machining that exceeds tool flute length, causing tool breakage or poor finish
**Why it happens:** Not checking tool.flute_length against feature depth
**How to avoid:** Filter tools where flute_length ≥ feature_depth × 1.2 (20% safety margin)
**Warning signs:** Depth-of-cut warnings in Fusion 360 CAM simulation

### Pitfall 6: Material Property Case Sensitivity
**What goes wrong:** Material lookup fails because "Aluminum" doesn't match "aluminum" in the SFM dictionary
**Why it happens:** String matching without normalization
**How to avoid:** Normalize material names to lowercase and replace spaces with underscores before lookup (following Phase 3 pattern)
**Warning signs:** Falling back to conservative default SFM (100) for common materials

### Pitfall 7: Feature Priority Group Assumptions
**What goes wrong:** Recommending milling operations before drilling, causing tools to wander into pre-drilled holes
**Why it happens:** Not respecting the machining priority groups from Phase 2 (drilling → roughing → finishing)
**How to avoid:** Process features in priority order; suggest drilling operations first, then roughing, then finishing
**Warning signs:** Toolpath simulation shows endmill entering holes, or user manually reorders operations

## Code Examples

Verified patterns from official sources:

### Material Library Structure
```python
# Source: Industry-standard SFM values
# https://www.cnclathing.com/cutting-speed-chart-for-different-materials-in-turning-drilling-and-more-cnc-machining-processes-cnclathing

MATERIAL_LIBRARY = {
    # Format: material_name: {sfm_hss, sfm_carbide, chip_load_range}
    "aluminum": {
        "sfm_hss": 400,
        "sfm_carbide": 1200,
        "chip_load_range": (0.001, 0.003),  # inches per tooth
        "hardness": "soft"
    },
    "mild_steel": {
        "sfm_hss": 100,
        "sfm_carbide": 300,
        "chip_load_range": (0.0005, 0.002),
        "hardness": "medium"
    },
    "stainless_steel": {
        "sfm_hss": 40,
        "sfm_carbide": 120,
        "chip_load_range": (0.0003, 0.001),
        "hardness": "hard"
    },
    "brass": {
        "sfm_hss": 300,
        "sfm_carbide": 900,
        "chip_load_range": (0.0008, 0.003),
        "hardness": "soft"
    },
    "plastic": {
        "sfm_hss": 500,
        "sfm_carbide": 1500,
        "chip_load_range": (0.001, 0.004),
        "hardness": "soft"
    }
}

def get_material_properties(material_name: str) -> dict:
    """Get material properties with fallback to conservative defaults."""
    key = material_name.lower().replace(" ", "_").replace("-", "_")

    # Try exact match first
    if key in MATERIAL_LIBRARY:
        return MATERIAL_LIBRARY[key]

    # Try partial match (e.g., "6061 aluminum" matches "aluminum")
    for mat_key, props in MATERIAL_LIBRARY.items():
        if mat_key in key or key in mat_key:
            return props

    # Conservative default for unknown materials
    return {
        "sfm_hss": 100,
        "sfm_carbide": 300,
        "chip_load_range": (0.0005, 0.001),
        "hardness": "medium"
    }
```

### Strategy Recommendation Response Format
```python
# Source: Established pattern from Phase 3 suggest_stock_setup
# Maintain consistency in suggestion response structure

def format_strategy_suggestion(features: list, material: str, tools: list) -> dict:
    """
    Format toolpath strategy suggestion response.

    Returns structured recommendation with:
    - Suggested operations per feature
    - Tool selections
    - Calculated feeds/speeds
    - Confidence and reasoning
    """
    suggestions = []

    for feature in features:
        # Map feature to operation
        operation_rec = map_feature_to_operation(feature, material)

        # Select tool
        tool_filter = "drill" if operation_rec["operation_type"] == "drilling" else "mill"
        tool_rec = select_best_tool(feature, tools, tool_filter)

        if "error" in tool_rec:
            suggestions.append({
                "feature": feature,
                "status": "error",
                "message": tool_rec["error"]
            })
            continue

        # Calculate feeds/speeds
        feeds_speeds = calculate_feeds_speeds(
            material=material,
            tool=tool_rec["tool"],
            is_carbide=True,
            operation_type="roughing" if "adaptive" in operation_rec["operation_type"] else "finishing"
        )

        suggestions.append({
            "feature": {
                "type": feature["type"],
                "id": feature.get("id"),
                "dimensions": {
                    "diameter": feature.get("diameter"),
                    "depth": feature.get("depth")
                }
            },
            "recommended_operation": {
                "type": operation_rec["operation_type"],
                "confidence": operation_rec["confidence"],
                "reasoning": operation_rec["reasoning"]
            },
            "recommended_tool": {
                "description": tool_rec["tool"]["description"],
                "diameter": tool_rec["tool"]["diameter"],
                "reasoning": tool_rec["reasoning"]
            },
            "cutting_parameters": {
                "rpm": feeds_speeds["rpm"],
                "feed_rate": feeds_speeds["feed_rate"],
                "stepover_roughing": {"value": tool_rec["stepover_roughing"], "unit": "mm"},
                "stepover_finishing": {"value": tool_rec["stepover_finishing"], "unit": "mm"}
            }
        })

    return {
        "status": "success",
        "material": material,
        "feature_count": len(features),
        "suggestions": suggestions,
        "source": "from: default_rules"  # or "from: user_preference" when preferences exist
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual CAM programmer selects all operations | CAM software suggests operations based on feature recognition | Fusion 360 ~2018-2020 | Reduces setup time but requires verification |
| Fixed SFM charts in books/tables | Dynamic feeds/speeds calculators with material databases | Industry shift ~2015+ | More accurate but requires tool material identification |
| 2D pocket clearing only | Adaptive clearing with constant engagement | Fusion 360 added ~2016 | 80-90% flute depth possible, faster roughing for hard materials |
| Separate roughing and finishing tools | Same tool for rough/finish with parameter changes | Modern CAM practice | Fewer tool changes, but requires conservative rough parameters |
| Metric vs imperial confusion | Explicit unit objects in responses | Phase 1 decision (2026-02-05) | Eliminates ambiguity in multi-unit workflows |

**Deprecated/outdated:**
- **Plunge-only drilling:** Modern CAM uses helical ramping for holes >3× diameter to reduce tool wear
- **Full-width slot milling:** Replaced by adaptive or trochoidal strategies to reduce side load
- **Fixed 50% stepover for all materials:** Material-specific stepover (soft=high, hard=low) is current practice

## Open Questions

Things that couldn't be fully resolved:

1. **Fusion 360 CAM strategy IDs for operation creation**
   - What we know: Strategies are retrieved via `setup.operations.compatibleStrategies` and have a `title` property
   - What's unclear: Exact string matching for common strategies ("2D Adaptive Clearing" vs "Adaptive Clearing") may vary by Fusion version
   - Recommendation: During implementation, query actual strategy titles and use fuzzy matching (e.g., `"adaptive" in strategy.title.lower()`)

2. **Tool material identification from tool library**
   - What we know: `tool.toJson()` returns tool properties including vendor and description
   - What's unclear: No explicit `material` field in the API; carbide vs HSS must be inferred from description text
   - Recommendation: Default to carbide (most common modern tooling) unless description contains "hss" or "high speed steel"

3. **Operation parameter name variations across Fusion versions**
   - What we know: Parameters are accessed via `itemByName("parameter_name")` and names can be discovered by Shift+hover in UI
   - What's unclear: Parameter names may change between Fusion 360 versions
   - Recommendation: Use try/except when setting parameters and log warnings for missing parameters rather than failing

4. **User preference for roughing vs finishing operations**
   - What we know: Some users prefer separate rough/finish ops, others prefer single-tool strategies
   - What's unclear: No established preference pattern yet (Phase 5 will address learning)
   - Recommendation: Phase 4 suggests both approaches; let user preference storage in Phase 5 capture actual choice

## Sources

### Primary (HIGH confidence)
- [Fusion 360 CAM API Introduction](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CAMIntroduction_UM.htm) - Official API documentation
- [Fusion 360 CAM Parameters](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CAMParameters_UM.htm) - Parameter-based operation configuration
- [Harvey Tool Speeds and Feeds 101](https://www.harveyperformance.com/in-the-loupe/speeds-and-feeds-101/) - Authoritative calculation formulas
- [CNCLATHING Cutting Speed Chart](https://www.cnclathing.com/cutting-speed-chart-for-different-materials-in-turning-drilling-and-more-cnc-machining-processes-cnclathing) - Material SFM values

### Secondary (MEDIUM confidence)
- [Adaptive Clearing vs Pocket Clearing - Medium](https://medium.com/@arstein/pockets-2d5fbc44bb99) - Strategy comparison verified with industry practice
- [CAMaster Toolpath Strategies](https://www.camaster.com/understanding-cnc-toolpath-strategies/) - Operation selection best practices
- [CNC Cookbook Stepover Guide](https://www.cnccookbook.com/cnc-stepover/) - Tool selection and stepover ratios
- [Fictiv CNC Stepover Guide](https://www.fictiv.com/articles/cnc-stepover-guide) - Stepover impact on surface finish
- [Machining Concepts Toolpath Strategies](https://machiningconceptserie.com/toolpath-strategies-for-maximum-efficiency-in-cnc-machining/) - Efficiency best practices

### Tertiary (LOW confidence - needs validation)
- [Python Rules Engine Options](https://www.nected.ai/us/blog-us/python-rule-engines-automate-and-enforce-with-python) - Surveyed but not recommended for this use case
- [Machining Knowledge Graph Research](https://www.mdpi.com/2075-1702/13/3/188) - Academic research on feature-operation mapping, not directly applicable to simple rule engine

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Fusion 360 API is authoritative, SQLite established in Phase 3
- Architecture: MEDIUM-HIGH - Patterns follow established Python/Fusion practices, but CAM parameter names need validation during implementation
- Feeds/speeds formulas: HIGH - Standard industry formulas verified across multiple authoritative sources
- Material SFM values: MEDIUM - Values are industry-standard starting points but may need shop-specific tuning
- Operation mapping rules: MEDIUM - Based on best practices and existing Phase 2 decisions, but edge cases will emerge with real-world parts
- Tool selection heuristics: HIGH - "Largest that fits" with 80% rule is industry standard and already applied in Phase 2

**Research date:** 2026-02-05
**Valid until:** ~60 days (stable domain - machining formulas don't change rapidly, but Fusion 360 API could evolve)

**Notes for planner:**
- No external Python dependencies required beyond stdlib and Fusion 360 API
- Leverage existing preference_store.py pattern from Phase 3 for strategy preferences
- Material library should be extensible (allow user-defined materials in future phases)
- Phase 4 provides SUGGESTIONS only; actual operation creation deferred to later phases
- Confidence scoring pattern from Phase 2 applies to strategy recommendations
