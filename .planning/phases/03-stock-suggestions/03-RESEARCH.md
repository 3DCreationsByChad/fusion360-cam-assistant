# Phase 3: Stock Suggestions - Research

**Researched:** 2026-02-05
**Domain:** Stock setup suggestion system with SQLite preferences for Fusion 360 CAM
**Confidence:** HIGH

## Summary

This research investigated how to implement stock setup suggestions based on geometry analysis, including stock dimension calculation from bounding box, standard stock size matching, orientation recommendations, and user preference storage in SQLite. The phase builds directly on Phase 2's geometry analysis and orientation scoring to suggest optimal stock configurations with source attribution.

The existing codebase already provides bounding box extraction, orientation analysis with setup sequences, and MCP bridge access to SQLite for preference storage. This phase adds stock dimension calculation with configurable offsets, standard size rounding (metric/imperial), cylindrical part detection, and a preference storage/retrieval system keyed by material + geometry type.

**Primary recommendation:** Implement `suggest_stock_setup` as a new handler in `cam_operations.py` that combines bounding box dimensions with configurable offsets (default 5mm XY, 2.5mm Z), rounds to standard stock sizes based on document units, leverages existing orientation analysis, and uses MCP bridge to store/retrieve preferences from SQLite with source attribution.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| adsk.fusion | Fusion 360 API | Bounding box, material info | Official API for geometry data |
| adsk.core | Fusion 360 API | Units, document properties | Document unit system detection |
| mcp.call("sqlite") | MCP Bridge | Preference storage/retrieval | Already integrated, thread-safe |
| json | Python stdlib | Response serialization | MCP protocol compliance |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| geometry_analysis | Local module | Orientation analysis | Reuse Phase 2 OrientationAnalyzer |
| typing | Python stdlib | Type hints | Structured preference representation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| MCP SQLite | Direct sqlite3 | MCP already configured, consistent with project architecture |
| Hardcoded stock sizes | External CSV/JSON | Hardcoded is simpler, can externalize later if needed |
| Material detection from body | User prompt | Body material may not be set; prompt when unknown per CONTEXT.md |

**Installation:**
```bash
# No installation needed - uses existing infrastructure
# SQLite accessed via MCP bridge (already available)
# Stock size tables embedded in module
```

## Architecture Patterns

### Recommended Project Structure
```
Fusion-360-MCP-Server/
├── cam_operations.py           # Add handle_suggest_stock_setup()
├── stock_suggestions/          # NEW: Stock suggestion utilities
│   ├── __init__.py
│   ├── stock_calculator.py     # Dimension calculation with offsets
│   ├── stock_sizes.py          # Standard size tables (metric/imperial)
│   ├── preference_store.py     # SQLite preference operations via MCP
│   └── cylindrical_detector.py # Detect lathe vs mill candidates
└── geometry_analysis/          # Existing (from Phase 2)
    ├── orientation_analyzer.py # Reuse for orientation suggestions
    └── ...
```

### Pattern 1: Stock Dimension Calculation with Offsets
**What:** Calculate stock dimensions from bounding box with configurable offsets
**When to use:** Every stock suggestion
**Example:**
```python
# Source: Industry standard machining allowances
def calculate_stock_dimensions(bbox, offsets=None, round_to_standard=True, unit_system="metric"):
    """
    Calculate stock dimensions from bounding box with machining allowances.

    Args:
        bbox: BoundingBox3D from body
        offsets: Dict with xy_mm and z_mm (default: 5.0 and 2.5)
        round_to_standard: Whether to round to standard stock sizes
        unit_system: "metric" or "imperial"

    Returns:
        Stock dimensions with source attribution
    """
    # Default offsets per CONTEXT.md and industry practice
    if offsets is None:
        offsets = {"xy_mm": 5.0, "z_mm": 2.5}

    # Extract bounding box dimensions (Fusion uses cm internally)
    part_x_mm = (bbox.maxPoint.x - bbox.minPoint.x) * 10
    part_y_mm = (bbox.maxPoint.y - bbox.minPoint.y) * 10
    part_z_mm = (bbox.maxPoint.z - bbox.minPoint.z) * 10

    # Apply offsets (XY offsets on all 4 sides, Z offset on top)
    stock_x_mm = part_x_mm + (offsets["xy_mm"] * 2)
    stock_y_mm = part_y_mm + (offsets["xy_mm"] * 2)
    stock_z_mm = part_z_mm + offsets["z_mm"]

    # Round to standard sizes if requested
    if round_to_standard:
        stock_x_mm = round_to_standard_size(stock_x_mm, unit_system)
        stock_y_mm = round_to_standard_size(stock_y_mm, unit_system)
        stock_z_mm = round_to_standard_size(stock_z_mm, unit_system)

    return {
        "width": {"value": stock_x_mm, "unit": "mm"},
        "depth": {"value": stock_y_mm, "unit": "mm"},
        "height": {"value": stock_z_mm, "unit": "mm"},
        "offsets_applied": offsets,
        "source": "from: default"  # Updated if from preference
    }
```

### Pattern 2: Standard Stock Size Tables
**What:** Round dimensions to nearest standard stock size based on unit system
**When to use:** When `round_to_standard=True` (default)
**Example:**
```python
# Source: Metric Metal, industrial stock suppliers
METRIC_PLATE_THICKNESSES_MM = [
    3, 4, 5, 6, 8, 10, 12, 15, 16, 18, 20, 22, 25, 30, 32, 35, 40, 45, 50,
    55, 60, 65, 70, 75, 80, 90, 100
]

METRIC_BAR_WIDTHS_MM = [
    10, 12, 15, 16, 18, 20, 22, 25, 30, 32, 35, 40, 45, 50, 55, 60, 65, 70,
    75, 80, 90, 100, 110, 120, 130, 140, 150, 160, 180, 200, 220, 250, 300
]

IMPERIAL_PLATE_THICKNESSES_IN = [
    0.125, 0.1875, 0.25, 0.3125, 0.375, 0.4375, 0.5, 0.625, 0.75, 0.875,
    1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 3.5, 4.0
]

IMPERIAL_BAR_WIDTHS_IN = [
    0.5, 0.625, 0.75, 0.875, 1.0, 1.125, 1.25, 1.375, 1.5, 1.75, 2.0, 2.25,
    2.5, 2.75, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 7.0, 8.0, 9.0, 10.0, 12.0
]

# Round bar diameters for cylindrical stock
METRIC_ROUND_DIAMETERS_MM = [
    6, 8, 10, 12, 14, 15, 16, 18, 20, 22, 25, 28, 30, 32, 35, 38, 40, 42,
    45, 48, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 110, 120, 130, 150
]

IMPERIAL_ROUND_DIAMETERS_IN = [
    0.25, 0.3125, 0.375, 0.4375, 0.5, 0.5625, 0.625, 0.75, 0.875, 1.0,
    1.125, 1.25, 1.375, 1.5, 1.625, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.5, 4.0
]

def round_to_standard_size(dimension_mm, unit_system, dimension_type="width"):
    """
    Round dimension to nearest larger standard stock size.

    Args:
        dimension_mm: Dimension in mm
        unit_system: "metric" or "imperial"
        dimension_type: "width", "thickness", or "round_diameter"

    Returns:
        Rounded dimension in mm
    """
    if unit_system == "metric":
        if dimension_type == "thickness":
            sizes = METRIC_PLATE_THICKNESSES_MM
        elif dimension_type == "round_diameter":
            sizes = METRIC_ROUND_DIAMETERS_MM
        else:
            sizes = METRIC_BAR_WIDTHS_MM

        # Find next larger standard size
        for size in sizes:
            if size >= dimension_mm:
                return size
        return sizes[-1]  # Return largest if all smaller

    else:  # imperial
        # Convert to inches for comparison
        dimension_in = dimension_mm / 25.4

        if dimension_type == "thickness":
            sizes = IMPERIAL_PLATE_THICKNESSES_IN
        elif dimension_type == "round_diameter":
            sizes = IMPERIAL_ROUND_DIAMETERS_IN
        else:
            sizes = IMPERIAL_BAR_WIDTHS_IN

        for size in sizes:
            if size >= dimension_in:
                return size * 25.4  # Return in mm
        return sizes[-1] * 25.4
```

### Pattern 3: Cylindrical Part Detection
**What:** Detect if part is suitable for round stock (lathe candidate)
**When to use:** For stock shape recommendation (round vs rectangular)
**Example:**
```python
# Source: Industry practice for lathe vs mill decision
def detect_cylindrical_part(body, features=None):
    """
    Detect if part is predominantly cylindrical (lathe candidate).

    Heuristics:
    1. Bounding box aspect: if two dimensions are similar and third is larger
       (elongated cylinder) or smaller (disc/flange)
    2. High proportion of cylindrical faces
    3. Feature analysis: mostly holes along axis, few pockets

    Args:
        body: BRepBody to analyze
        features: Optional list of detected features from Phase 2

    Returns:
        Dict with:
        - is_cylindrical: bool
        - confidence: float (0-1)
        - reasoning: str
        - cylinder_axis: "X", "Y", or "Z" (if cylindrical)
        - enclosing_diameter: float (mm)
    """
    bbox = body.boundingBox

    # Get dimensions (convert cm to mm)
    x_mm = (bbox.maxPoint.x - bbox.minPoint.x) * 10
    y_mm = (bbox.maxPoint.y - bbox.minPoint.y) * 10
    z_mm = (bbox.maxPoint.z - bbox.minPoint.z) * 10

    dims = sorted([(x_mm, "X"), (y_mm, "Y"), (z_mm, "Z")])

    # Check for cylindrical aspect ratio
    # Cylindrical if two smallest dims are similar (within 20%)
    # OR two largest dims are similar (disc shape)

    min1, min2, max_dim = dims[0][0], dims[1][0], dims[2][0]

    # Elongated cylinder: min1 ~ min2, both << max
    elongated_ratio = min2 / min1 if min1 > 0 else 0
    elongated_score = 1.0 if elongated_ratio >= 0.8 and elongated_ratio <= 1.25 else 0.5

    # Calculate enclosing diameter (diagonal of smaller cross-section)
    import math
    enclosing_diameter = math.sqrt(min1**2 + min2**2)

    # Determine likely axis (perpendicular to two similar dimensions)
    if elongated_score > 0.8:
        axis = dims[2][1]  # Axis is along longest dimension
    else:
        axis = dims[0][1]  # Axis is along shortest (disc)

    # Check cylindrical face ratio
    cylindrical_face_count = 0
    total_face_count = 0

    try:
        for face in body.faces:
            total_face_count += 1
            geom = face.geometry
            if isinstance(geom, adsk.core.Cylinder):
                cylindrical_face_count += 1
    except:
        pass

    face_ratio = cylindrical_face_count / max(total_face_count, 1)

    # Combine scores
    # High face ratio AND elongated aspect = likely cylindrical
    is_cylindrical = (face_ratio > 0.4 and elongated_score > 0.7)
    confidence = min((face_ratio * 0.6) + (elongated_score * 0.4), 1.0)

    if is_cylindrical:
        reasoning = f"Part appears cylindrical: {cylindrical_face_count}/{total_face_count} cylindrical faces, aspect ratio suggests {axis}-axis rotation"
    else:
        reasoning = f"Part appears prismatic: only {cylindrical_face_count}/{total_face_count} cylindrical faces"

    return {
        "is_cylindrical": is_cylindrical,
        "confidence": round(confidence, 2),
        "reasoning": reasoning,
        "cylinder_axis": axis if is_cylindrical else None,
        "enclosing_diameter_mm": round(enclosing_diameter, 3)
    }
```

### Pattern 4: SQLite Preference Storage via MCP Bridge
**What:** Store and retrieve preferences using MCP SQLite tool
**When to use:** All preference operations
**Example:**
```python
# Source: MCP bridge pattern from mcp_bridge.py
def get_preference(material: str, geometry_type: str, mcp) -> dict:
    """
    Retrieve stock preference from SQLite.

    Args:
        material: Material name (e.g., "aluminum", "steel")
        geometry_type: Geometry classification (e.g., "pocket-heavy", "hole-heavy", "mixed")
        mcp: MCP bridge module with call() function

    Returns:
        Preference dict with source attribution, or None if not found
    """
    result = mcp.call("sqlite", {
        "input": {
            "sql": """
                SELECT offsets_xy_mm, offsets_z_mm, preferred_orientation,
                       stock_shape, machining_allowance_mm, created_at
                FROM cam_stock_preferences
                WHERE material = ? AND geometry_type = ?
                ORDER BY created_at DESC
                LIMIT 1
            """,
            "params": [material.lower(), geometry_type.lower()],
            "tool_unlock_token": "29e63eb5"
        }
    })

    if result and result.get("rows") and len(result["rows"]) > 0:
        row = result["rows"][0]
        return {
            "offsets": {
                "xy_mm": row[0],
                "z_mm": row[1]
            },
            "preferred_orientation": row[2],
            "stock_shape": row[3],
            "machining_allowance_mm": row[4],
            "source": "from: user_preference"
        }

    return None


def save_preference(material: str, geometry_type: str, preference: dict, mcp) -> bool:
    """
    Save stock preference to SQLite.

    Args:
        material: Material name
        geometry_type: Geometry classification
        preference: Dict with offsets, orientation, shape, allowance
        mcp: MCP bridge module

    Returns:
        True if saved successfully
    """
    result = mcp.call("sqlite", {
        "input": {
            "sql": """
                INSERT OR REPLACE INTO cam_stock_preferences
                (material, geometry_type, offsets_xy_mm, offsets_z_mm,
                 preferred_orientation, stock_shape, machining_allowance_mm)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            "params": [
                material.lower(),
                geometry_type.lower(),
                preference.get("offsets", {}).get("xy_mm", 5.0),
                preference.get("offsets", {}).get("z_mm", 2.5),
                preference.get("preferred_orientation"),
                preference.get("stock_shape", "rectangular"),
                preference.get("machining_allowance_mm")
            ],
            "tool_unlock_token": "29e63eb5"
        }
    })

    return result is not None and not result.get("error")
```

### Pattern 5: Prompt for Missing Preferences
**What:** Request user input when preference doesn't exist or confidence is low
**When to use:** Per CONTEXT.md - interactive prompting, not silent defaults
**Example:**
```python
def suggest_stock_with_prompt_handling(body, material, mcp):
    """
    Suggest stock setup, prompting for preferences when needed.

    Per CONTEXT.md: When no matching preference exists, prompt user
    to establish preference for this combination.
    """
    # Classify geometry type from features
    geometry_type = classify_geometry_type(body)  # e.g., "pocket-heavy"

    # Try to get existing preference
    preference = get_preference(material, geometry_type, mcp)

    if preference is None:
        # No preference exists - need to prompt user
        return {
            "status": "preference_needed",
            "message": f"No stock preferences found for {material} + {geometry_type}. Please establish preferences.",
            "material": material,
            "geometry_type": geometry_type,
            "suggested_defaults": {
                "offsets": {"xy_mm": 5.0, "z_mm": 2.5},
                "stock_shape": "rectangular",
                "preferred_orientation": None  # Will use best from analysis
            },
            "action_required": "Call with 'save_preference: true' to store your choices"
        }

    # Preference exists - use it
    return calculate_stock_with_preference(body, preference)
```

### Pattern 6: Response Structure with Setup Sequence
**What:** Include setup sequence with every stock suggestion per CONTEXT.md
**When to use:** All stock suggestions, even single-setup parts
**Example:**
```python
def format_stock_suggestion_response(stock_dims, orientation, cylindrical_info, source):
    """
    Format complete stock suggestion response.

    Per CONTEXT.md: Always include setup sequence with every suggestion.
    """
    return {
        "stock_dimensions": {
            "rectangular": {
                "width": stock_dims["width"],
                "depth": stock_dims["depth"],
                "height": stock_dims["height"]
            },
            # Include round option for cylindrical parts
            "round": {
                "diameter": cylindrical_info["enclosing_diameter_mm"],
                "length": stock_dims["height"]
            } if cylindrical_info["is_cylindrical"] else None
        },
        "recommended_shape": "round" if cylindrical_info["is_cylindrical"] else "rectangular",
        "shape_trade_offs": {
            "rectangular": "More stable fixturing, easier to clamp",
            "round": "Less material waste, faster for cylindrical parts"
        } if cylindrical_info["is_cylindrical"] else None,
        "orientation": {
            "recommended": orientation["axis"],
            "score": orientation["score"],
            "reasoning": orientation["reasoning"],
            "alternatives": orientation.get("alternatives", [])
        },
        "setup_sequence": orientation["setup_sequence"],
        "offsets_applied": stock_dims["offsets_applied"],
        "source": source,  # "from: user_preference" or "from: default"
        "confidence": orientation.get("confidence", 0.9)
    }
```

### Anti-Patterns to Avoid
- **Silent defaults when preferences missing:** Per CONTEXT.md, prompt user to establish preference
- **Ignoring unit system:** Always detect from document and convert appropriately
- **Hardcoding orientation without Phase 2 analysis:** Reuse OrientationAnalyzer for consistency
- **Skipping setup sequence for single-setup parts:** CONTEXT.md requires it always
- **Not rounding to standard sizes:** Real shops work with standard stock
- **Missing source attribution:** User needs to know if suggestion came from preference or default

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Orientation scoring | Custom orientation logic | OrientationAnalyzer from Phase 2 | Already optimized, consistent with geometry analysis |
| Feature-based geometry classification | New classification logic | Features from analyze_geometry_for_cam | Phase 2 already detects pockets, holes, slots |
| Confidence scoring | Ad-hoc confidence values | confidence_scorer module | Consistent thresholds across system |
| Database operations | Direct sqlite3 | mcp.call("sqlite") | Already integrated, handles threading |
| Unit conversion | Custom converters | Existing _to_mm_unit helper | Consistent format {"value": X, "unit": "mm"} |
| Bounding box | Custom iteration | body.boundingBox | Fusion API provides GPU-accelerated version |

**Key insight:** This phase is mostly composition of existing capabilities. The stock suggestion system combines Phase 2's geometry analysis with new offset/rounding logic and preference storage. Avoid reimplementing what Phase 2 already provides.

## Common Pitfalls

### Pitfall 1: Document Unit Detection Failure
**What goes wrong:** Stock sizes rounded to metric when document is imperial, or vice versa
**Why it happens:** Fusion documents have unit settings that should drive stock size rounding
**How to avoid:** Check `design.unitsManager.defaultLengthUnits` to detect document unit system. Common values: "mm" (metric), "in" (imperial)
**Warning signs:** User complains stock sizes don't match their shop's standard stock

### Pitfall 2: Preference Key Collision
**What goes wrong:** Preferences from different materials/geometries overwrite each other
**Why it happens:** Insufficient key specificity in preference lookup
**How to avoid:** Key preferences by material + geometry_type combination (e.g., "aluminum + pocket-heavy"). Use lowercase normalization.
**Warning signs:** User's preference for aluminum being used for steel parts

### Pitfall 3: SQLite Table Not Initialized
**What goes wrong:** Preference queries fail with "table does not exist" error
**Why it happens:** Schema not initialized before first use
**How to avoid:** Check for table existence on first call; create if missing. Include schema creation in handler initialization.
**Warning signs:** First preference save fails; subsequent calls work after manual table creation

### Pitfall 4: Orientation Confidence Not Propagated
**What goes wrong:** Low-confidence orientation used without prompting user
**Why it happens:** Only checking stock confidence, not orientation confidence
**How to avoid:** Per CONTEXT.md, when orientation confidence is low, ask user to choose before returning stock suggestion. Check OrientationAnalyzer score thresholds.
**Warning signs:** User surprised by orientation choice; didn't realize they could have chosen differently

### Pitfall 5: Ignoring Cylindrical Trade-offs
**What goes wrong:** Only suggesting round stock without explaining rectangular option
**Why it happens:** Binary cylindrical detection without nuance
**How to avoid:** Per CONTEXT.md, for cylindrical parts show BOTH round and rectangular options with trade-offs. Let user decide based on shop capabilities.
**Warning signs:** User asks "can't I just use rectangular stock for this?"

### Pitfall 6: Offset Application Asymmetry
**What goes wrong:** Z offset applied to both top and bottom, doubling stock height unnecessarily
**Why it happens:** Confusion about machining allowance vs. full-part offset
**How to avoid:** XY offset is per-side (total = 2x offset). Z offset is typically top-only (workholding from bottom). Document clearly in response.
**Warning signs:** Suggested stock much taller than needed

## Code Examples

Verified patterns from official sources and existing codebase:

### Complete suggest_stock_setup Handler
```python
# Source: Integration of patterns above with existing cam_operations.py structure
def handle_suggest_stock_setup(arguments: dict) -> dict:
    """
    Suggest stock setup based on geometry analysis.

    Arguments:
        body_name (str, optional): Specific body to analyze (default: first body)
        material (str, optional): Material for preference lookup
        save_preference (bool): If true, save suggested values as preference
        custom_offsets (dict): Override default offsets {xy_mm, z_mm}
        round_to_standard (bool): Round to standard stock sizes (default: true)

    Returns:
        Stock suggestion with dimensions, orientation, setup sequence, and source
    """
    try:
        app = _get_app()
        design = adsk.fusion.Design.cast(app.activeProduct)

        if not design:
            return _format_error("No active design")

        # Get body to analyze
        body_name = arguments.get('body_name')
        body = None

        if body_name:
            for b in design.rootComponent.bRepBodies:
                if b.name == body_name:
                    body = b
                    break
            if not body:
                return _format_error(f"Body '{body_name}' not found")
        else:
            bodies = list(design.rootComponent.bRepBodies)
            if not bodies:
                return _format_error("No bodies in design")
            body = bodies[0]

        # Detect unit system from document
        unit_system = "metric"
        try:
            units = design.unitsManager.defaultLengthUnits
            if "in" in units.lower():
                unit_system = "imperial"
        except:
            pass

        # Get material (from body or argument)
        material = arguments.get('material')
        if not material and body.material:
            material = body.material.name.lower()
        if not material:
            material = "unknown"

        # Analyze geometry using Phase 2 infrastructure
        # ... (call analyze_geometry_for_cam or use FeatureDetector)

        # Classify geometry type from features
        geometry_type = _classify_geometry_type(features)

        # Check for existing preference
        preference = _get_preference(material, geometry_type)

        if preference is None and not arguments.get('use_defaults'):
            # Per CONTEXT.md: prompt user when no preference exists
            return _format_response({
                "status": "preference_needed",
                "message": f"No preferences for '{material} + {geometry_type}'",
                "material": material,
                "geometry_type": geometry_type,
                "suggested_defaults": {
                    "offsets": {"xy_mm": 5.0, "z_mm": 2.5},
                    "stock_shape": "rectangular"
                }
            })

        # Use preference or defaults
        offsets = arguments.get('custom_offsets') or \
                  (preference and preference.get("offsets")) or \
                  {"xy_mm": 5.0, "z_mm": 2.5}

        # Calculate stock dimensions
        stock_dims = _calculate_stock_dimensions(
            body.boundingBox,
            offsets,
            arguments.get('round_to_standard', True),
            unit_system
        )

        # Get orientation from Phase 2 analyzer
        orientation = _get_best_orientation(body, features)

        # Check orientation confidence per CONTEXT.md
        if orientation["score"] < 0.7:  # Low confidence threshold
            return _format_response({
                "status": "orientation_choice_needed",
                "message": "Orientation confidence is low. Please select preferred orientation.",
                "options": orientation["alternatives"],
                "stock_dimensions": stock_dims
            })

        # Detect cylindrical parts
        cylindrical = _detect_cylindrical_part(body, features)

        # Build response
        source = preference["source"] if preference else "from: default"

        result = _format_stock_suggestion_response(
            stock_dims, orientation, cylindrical, source
        )

        # Save preference if requested
        if arguments.get('save_preference'):
            _save_preference(material, geometry_type, {
                "offsets": offsets,
                "preferred_orientation": orientation["axis"],
                "stock_shape": "round" if cylindrical["is_cylindrical"] else "rectangular"
            })
            result["preference_saved"] = True

        return _format_response(result)

    except Exception as e:
        import traceback
        return _format_error(f"Failed to suggest stock: {str(e)}", traceback.format_exc())
```

### SQLite Schema Initialization
```python
# Source: MCP SQLite documentation + preference storage requirements
STOCK_PREFERENCES_SCHEMA = """
CREATE TABLE IF NOT EXISTS cam_stock_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material TEXT NOT NULL,
    geometry_type TEXT NOT NULL,
    offsets_xy_mm REAL DEFAULT 5.0,
    offsets_z_mm REAL DEFAULT 2.5,
    preferred_orientation TEXT,
    stock_shape TEXT DEFAULT 'rectangular',
    machining_allowance_mm REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(material, geometry_type)
);

CREATE INDEX IF NOT EXISTS idx_stock_pref_material_geo
ON cam_stock_preferences(material, geometry_type);
"""

MACHINE_PROFILES_SCHEMA = """
CREATE TABLE IF NOT EXISTS cam_machine_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    machine_type TEXT NOT NULL,
    max_x_mm REAL,
    max_y_mm REAL,
    max_z_mm REAL,
    spindle_max_rpm INTEGER,
    has_4th_axis INTEGER DEFAULT 0,
    has_5th_axis INTEGER DEFAULT 0,
    post_processor TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

def initialize_schema(mcp):
    """Initialize SQLite schema via MCP bridge."""
    # Create preferences table
    mcp.call("sqlite", {
        "input": {
            "sql": STOCK_PREFERENCES_SCHEMA,
            "tool_unlock_token": "29e63eb5"
        }
    })

    # Create machine profiles table
    mcp.call("sqlite", {
        "input": {
            "sql": MACHINE_PROFILES_SCHEMA,
            "tool_unlock_token": "29e63eb5"
        }
    })
```

### Geometry Type Classification
```python
# Source: Based on Phase 2 feature detection patterns
def _classify_geometry_type(features: list) -> str:
    """
    Classify geometry by dominant feature type.

    Returns one of:
    - "pocket-heavy": Mostly pockets/slots
    - "hole-heavy": Mostly holes
    - "mixed": Balanced mix
    - "simple": Few features
    """
    if not features:
        return "simple"

    hole_count = sum(1 for f in features if f.get("type") == "hole")
    pocket_count = sum(1 for f in features if f.get("type") in ["pocket", "slot"])
    total = hole_count + pocket_count

    if total < 3:
        return "simple"

    hole_ratio = hole_count / total if total > 0 else 0

    if hole_ratio > 0.7:
        return "hole-heavy"
    elif hole_ratio < 0.3:
        return "pocket-heavy"
    else:
        return "mixed"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixed stock offsets | Preference-based configurable offsets | Modern CAM systems (2020+) | Shop-specific optimization |
| Manual stock size lookup | Automatic rounding to standard sizes | Industrial automation | Reduces material sourcing friction |
| Single orientation suggestion | Ranked alternatives with scores | Phase 2 implementation | User-informed decisions |
| Boolean cylindrical detection | Confidence-scored with trade-offs | Current best practice | Nuanced recommendations |
| Hardcoded defaults | SQLite-backed preferences | Current implementation | Learning system foundation |

**Deprecated/outdated:**
- **Fixed 5mm offset for all materials:** Different materials need different allowances (aluminum more forgiving than titanium)
- **Single stock shape suggestion:** Modern practice shows alternatives with trade-offs
- **No source attribution:** Users need to know where suggestions come from to build trust

## Open Questions

Things that couldn't be fully resolved:

1. **Threshold for "close alternatives" in orientation**
   - What we know: CONTEXT.md suggests 10-15% score gap
   - What's unclear: Optimal threshold for user experience
   - Recommendation: Use 15% (0.15 score difference) initially, make configurable. If top two orientations are within 15%, show both as "close alternatives"

2. **Standard stock sizes completeness**
   - What we know: Compiled common metric/imperial sizes from suppliers
   - What's unclear: May not cover all regional standards or specialty materials
   - Recommendation: Use provided tables as starting point; add logging when user accepts non-standard size to learn gaps

3. **Material name normalization**
   - What we know: Fusion body.material.name returns varied formats
   - What's unclear: Complete list of possible material names from Fusion library
   - Recommendation: Normalize to lowercase, strip prefixes like "Generic " or "Autodesk ", use fuzzy matching for preference lookup

4. **Machine profile integration**
   - What we know: Schema includes cam_machine_profiles table
   - What's unclear: How machine limits should constrain stock suggestions
   - Recommendation: Defer to Phase 6 (Post-Processor); create table now but don't query it yet

## Sources

### Primary (HIGH confidence)
- Existing codebase: `cam_operations.py`, `geometry_analysis/` - Verified patterns
- [Fusion 360 API Documentation](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/BRepBody.htm) - BoundingBox, material properties
- MCP Bridge: `lib/mcp_bridge.py` - SQLite access pattern
- Phase 2 RESEARCH.md - OrientationAnalyzer, confidence scoring patterns

### Secondary (MEDIUM confidence)
- [Metric Metal - Aluminum Plate](https://www.metricmetal.com/product/aluminum/plate-aluminum/) - Standard metric thicknesses
- [Chalco Aluminum - Plate Thickness Chart](https://www.chalcoaluminum.com/knowledge/plate-thick/) - Common stock sizes
- [3ERP - Machining Allowance](https://www.3erp.com/blog/machining-allowance/) - Standard offset practices (3-5mm for milling)
- [WayKen - Bar vs Plate Stock](https://waykenrm.com/blogs/bar-vs-plate/) - Round vs rectangular selection criteria

### Tertiary (LOW confidence)
- WebSearch for specific stock sizes - Needs validation with local suppliers
- Cylindrical detection heuristics - Industry practice, needs calibration with real parts

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Uses existing infrastructure (MCP bridge, Phase 2 analyzers)
- Architecture: HIGH - Follows established patterns from Phase 2, cam_operations.py
- Stock size tables: MEDIUM - Compiled from suppliers, may need regional adjustment
- Cylindrical detection: MEDIUM - Heuristic-based, needs real-world validation
- Pitfalls: HIGH - Based on CONTEXT.md requirements and common CAM mistakes

**Research date:** 2026-02-05
**Valid until:** 2026-04-05 (60 days) - Stock sizes stable; preference schema unlikely to change

**Research constraints from CONTEXT.md:**
- Orientation recommendation logic: LOCKED - Return best + close alternatives, prompt when low confidence
- Preference keying: LOCKED - material + geometry type combination
- Setup sequence: LOCKED - Always include, even for single-setup parts
- Source attribution: LOCKED - Always show "from: user_preference" or "from: default"
- Interactive prompting: LOCKED - Prompt when no preference or low confidence
- Cylindrical trade-offs: LOCKED - Show both round and rectangular options
- Close alternatives threshold: DISCRETION - Recommend 15% gap (configurable)
- Standard stock size tables: DISCRETION - Provided tables, can extend
- SQLite schema details: DISCRETION - Schema provided in examples
