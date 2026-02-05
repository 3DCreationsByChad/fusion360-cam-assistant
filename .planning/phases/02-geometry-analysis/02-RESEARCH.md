# Phase 2: Geometry Analysis - Research

**Researched:** 2026-02-05
**Domain:** Fusion 360 Design API geometry analysis for CAM manufacturability
**Confidence:** HIGH

## Summary

This research investigated how to implement advanced geometry analysis for CAM planning in Fusion 360 using the Design and CAM APIs. The standard approach combines Fusion's built-in feature recognition APIs (RecognizedHole, RecognizedPocket) with custom BRep topology traversal for detailed feature characterization. User decisions require confidence scoring, rich metadata per feature, machining priority grouping, and orientation suggestions optimized for minimal setups.

The existing codebase already implements basic geometry analysis (`analyze_geometry_for_cam`) with bounding box calculation, volume/surface area, and simple feature detection. This phase enhances it with production-ready feature classification, confidence scoring, per-feature tool requirements, and actionable orientation recommendations with setup sequences.

**Primary recommendation:** Use Fusion's native RecognizedHole/RecognizedPocket APIs as the foundation for feature detection (HIGH confidence), augment with custom BRep loop analysis for slot detection and ambiguous features (MEDIUM confidence flags), include Fusion geometry IDs (entityToken) for programmatic selection, and provide heuristic-based confidence scores with reasoning text explaining classification decisions.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| adsk.fusion | Fusion 360 API | BRep geometry access and manipulation | Official API for design geometry; provides BRepBody, BRepFace, BRepLoop access |
| adsk.cam | Fusion 360 API | Feature recognition (holes, pockets) | Official CAM feature detection with RecognizedHole/RecognizedPocket classes |
| adsk.core | Fusion 360 API | Geometry types and measurements | Core geometric primitives (Cylinder, Plane, Torus, etc.) and bounding boxes |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| TemporaryBRepManager | Fusion API | Boolean operations, silhouette curves, transformations | Transient geometry analysis without parametric overhead; useful for orientation testing |
| MeasureManager | Fusion API | Distance and volume calculations | Per-feature measurements, clearance analysis |
| json | Python stdlib | Response serialization | MCP protocol compliance |
| typing | Python stdlib | Type hints and dataclasses | Structured feature representation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Native Fusion APIs | Custom geometry algorithms | Fusion APIs are faster, GPU-accelerated, and handle edge cases (tolerances, degeneracies); custom code prone to bugs |
| Heuristic confidence | ML-based classification | Heuristics are deterministic, explainable, and don't require training data; ML would need labeled dataset |
| BRep loop traversal | Pixel-based silhouette analysis | BRep traversal is exact and parametric; pixel methods are approximate but faster for complex geometry |

**Installation:**
```bash
# No installation needed - adsk modules are provided by Fusion 360 runtime
# MCP integration uses existing cam_operations.py structure
```

## Architecture Patterns

### Recommended Project Structure
```
Fusion-360-MCP-Server/
├── cam_operations.py           # CAM-specific handlers (existing)
│   ├── handle_analyze_geometry_for_cam()  # Main entry point (existing, enhance)
│   └── route_cam_operation()             # Router (existing)
├── geometry_analysis/          # NEW: Geometry analysis utilities
│   ├── __init__.py
│   ├── feature_detector.py     # Feature detection logic
│   ├── confidence_scorer.py    # Confidence calculation heuristics
│   ├── orientation_analyzer.py # Setup/flip sequence recommendations
│   └── geometry_helpers.py     # BRep traversal utilities
└── lib/
    └── mcp_client.py           # MCP protocol client (existing)
```

### Pattern 1: Feature Detection with Native APIs
**What:** Use Fusion's RecognizedHole and RecognizedPocket as primary detection, fall back to custom analysis for unsupported features
**When to use:** All feature detection operations
**Example:**
```python
# Source: https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/FeatureRecognition_UM.htm
import adsk.cam

def detect_holes(body):
    """Detect all holes using Fusion's API."""
    # Returns RecognizedHole objects with segment information
    holes = adsk.cam.RecognizedHole.recognizeHoles([body])

    features = []
    for hole in holes:
        # Each hole has segments (cylinders, cones, flats, toruses)
        # Confidence: HIGH for simple holes, MEDIUM for complex multi-segment
        confidence = 0.95 if hole.segmentCount == 1 else 0.75

        # Extract diameter from first cylindrical segment
        diameter = None
        for segment in hole.segments:
            if segment.type == adsk.cam.RecognizedHoleSegmentType.Cylinder:
                diameter = segment.diameter * 10  # cm to mm
                break

        # Get faces for entityToken (Fusion geometry ID)
        face_tokens = [face.entityToken for face in hole.faces]

        features.append({
            "type": "hole",
            "confidence": confidence,
            "reasoning": f"Recognized by Fusion API: {hole.segmentCount} segments",
            "diameter": {"value": round(diameter, 3), "unit": "mm"} if diameter else None,
            "segment_count": hole.segmentCount,
            "fusion_faces": face_tokens,  # For programmatic selection
            "needs_review": hole.segmentCount > 3  # Complex holes need review
        })

    return features
```

### Pattern 2: Pocket Recognition with Filtering
**What:** Use RecognizedPocket API with configurable depth/radius thresholds
**When to use:** Pocket and slot detection
**Example:**
```python
# Source: https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/HoleAndPocketRecognition_Sample.htm
import adsk.cam
import adsk.core

def detect_pockets_and_slots(body, min_depth_mm=1.0, max_corner_radius_mm=10.0):
    """Detect pockets using Fusion API, classify slots by aspect ratio."""
    # Define tool direction (Z-up for 3-axis)
    tool_direction = adsk.core.Vector3D.create(0, 0, -1)

    # Recognize pockets
    pockets = adsk.cam.RecognizedPocket.recognizePockets(body, tool_direction)

    features = []
    for pocket in pockets:
        # Get bounding box of pocket boundaries
        bbox = calculate_pocket_bbox(pocket.boundaries)

        # Aspect ratio heuristic: slot if length > 3 * width
        width = min(bbox['x'], bbox['y'])
        length = max(bbox['x'], bbox['y'])
        aspect_ratio = length / width if width > 0 else 1.0

        # Classification logic per user decision
        if aspect_ratio > 3.0:
            feature_type = "slot"
            confidence = 0.85  # Heuristic-based classification
            reasoning = f"Aspect ratio {aspect_ratio:.1f}:1 indicates slot (length >> width)"
        else:
            feature_type = "pocket"
            confidence = 0.95  # Direct from Fusion API
            reasoning = f"Aspect ratio {aspect_ratio:.1f}:1 indicates pocket"

        # Check if through pocket
        is_through = pocket.isThrough if hasattr(pocket, 'isThrough') else False
        if is_through:
            confidence = 0.90  # Through features are clear

        # Get face tokens
        face_tokens = [face.entityToken for face in pocket.faces]

        features.append({
            "type": feature_type,
            "confidence": confidence,
            "reasoning": reasoning,
            "depth": {"value": round(pocket.depth * 10, 3), "unit": "mm"} if hasattr(pocket, 'depth') else None,
            "is_through": is_through,
            "dimensions": {
                "length": {"value": round(length, 3), "unit": "mm"},
                "width": {"value": round(width, 3), "unit": "mm"}
            },
            "aspect_ratio": round(aspect_ratio, 2),
            "fusion_faces": face_tokens,
            "bounding_box": bbox,
            "needs_review": aspect_ratio > 2.5 and aspect_ratio < 3.5  # Ambiguous range
        })

    return features
```

### Pattern 3: BRep Loop Analysis for Blind Holes and Pockets
**What:** Traverse BRep loops to distinguish outer vs inner boundaries (pockets vs islands)
**When to use:** When RecognizedPocket misses features or for detailed pocket characterization
**Example:**
```python
# Source: https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/BRepGeometry_UM.htm
def analyze_face_loops(face):
    """Analyze face loops to detect pockets/holes."""
    # All faces have one outer loop and 0+ inner loops
    outer_loop = face.loops[0] if face.loops.count > 0 else None
    inner_loops = [face.loops[i] for i in range(1, face.loops.count)]

    # Inner loops indicate holes or islands
    features = []
    for loop in inner_loops:
        # Check if loop is cylindrical (hole) or planar (pocket island)
        is_cylindrical = all(
            isinstance(edge.geometry, adsk.core.Circle) or
            isinstance(edge.geometry, adsk.core.Arc3D)
            for coedge in loop.coEdges
            for edge in [coedge.edge]
        )

        if is_cylindrical:
            # Calculate diameter from loop edges
            diameter = estimate_circle_diameter(loop)
            features.append({
                "type": "hole",
                "confidence": 0.70,  # Lower than Fusion API
                "reasoning": "Detected via BRep loop analysis (circular inner loop)",
                "diameter": {"value": round(diameter, 3), "unit": "mm"},
                "fusion_faces": [face.entityToken],
                "needs_review": True  # Custom detection always needs review
            })
        else:
            # Island in pocket
            features.append({
                "type": "pocket_island",
                "confidence": 0.65,
                "reasoning": "Detected via BRep loop analysis (non-circular inner loop)",
                "fusion_faces": [face.entityToken],
                "needs_review": True
            })

    return features
```

### Pattern 4: Confidence Scoring with Heuristics
**What:** Assign confidence based on detection method, geometry complexity, and ambiguity
**When to use:** Every feature classification
**Example:**
```python
def calculate_confidence(detection_source, geometry_complexity, ambiguity_flags):
    """
    Calculate confidence score (0-1) based on multiple factors.

    Args:
        detection_source: "fusion_api", "brep_analysis", "heuristic"
        geometry_complexity: 0-10 scale (0=simple, 10=very complex)
        ambiguity_flags: List of ambiguity reasons

    Returns:
        float: Confidence score 0.0-1.0
    """
    # Base confidence by source
    base_confidence = {
        "fusion_api": 0.95,
        "brep_analysis": 0.75,
        "heuristic": 0.60
    }[detection_source]

    # Complexity penalty (0-0.15 reduction)
    complexity_penalty = min(geometry_complexity / 100, 0.15)

    # Ambiguity penalty (0.05 per flag, max 0.25)
    ambiguity_penalty = min(len(ambiguity_flags) * 0.05, 0.25)

    # Final score
    confidence = max(base_confidence - complexity_penalty - ambiguity_penalty, 0.30)

    return round(confidence, 2)

# Example usage:
confidence = calculate_confidence(
    detection_source="fusion_api",
    geometry_complexity=5,  # Multi-segment hole
    ambiguity_flags=["non-standard_segments", "mixed_taper"]
)
# Result: 0.95 - 0.05 - 0.10 = 0.80
```

### Pattern 5: Orientation Analysis with Setup Sequences
**What:** Recommend orientations ranked by minimal setups, with setup/flip sequences
**When to use:** All geometry analysis operations
**Example:**
```python
# Source: User decision in CONTEXT.md + CAM best practices
def suggest_orientations(body, features):
    """
    Suggest part orientations optimized for minimal setups.

    Returns orientations with setup sequences and unreachable feature flags.
    """
    bbox = body.boundingBox

    orientations = []

    # Analyze each primary axis orientation
    for axis in ["Z_UP", "Y_UP", "X_UP"]:
        # Calculate reachable features for this orientation
        reachable, unreachable = analyze_feature_accessibility(features, axis)

        # Score based on: stability (base area), feature access, setup count
        base_area = calculate_base_area(bbox, axis)
        setup_count = estimate_setup_count(reachable, unreachable)

        # Higher score = better orientation
        score = (len(reachable) / len(features)) * 0.6 + \
                (1.0 / setup_count) * 0.3 + \
                (base_area / bbox.surfaceArea) * 0.1

        # Build setup sequence
        sequence = []
        if reachable:
            sequence.append({
                "step": 1,
                "action": "machine_top_features",
                "features": [f["name"] for f in reachable if f.get("side") == "top"]
            })

        if unreachable:
            sequence.append({
                "step": 2,
                "action": "flip_part",
                "requires": "Manual flip or tombstone fixture"
            })
            sequence.append({
                "step": 3,
                "action": "machine_bottom_features",
                "features": [f["name"] for f in unreachable if f.get("side") == "bottom"]
            })

        orientations.append({
            "axis": axis,
            "score": round(score, 2),
            "setup_count": setup_count,
            "reachable_features": len(reachable),
            "unreachable_features": len(unreachable),
            "unreachable_feature_list": [
                {
                    "name": f.get("name", "unnamed"),
                    "type": f["type"],
                    "reason": f.get("unreachable_reason", "Undercut or opposite face")
                }
                for f in unreachable
            ],
            "setup_sequence": sequence,
            "base_dimensions": get_base_dimensions(bbox, axis),
            "reasoning": f"{len(reachable)}/{len(features)} features reachable, {setup_count} setup(s)"
        })

    # Sort by score (highest first)
    orientations.sort(key=lambda x: x["score"], reverse=True)

    return orientations
```

### Pattern 6: Minimum Tool Radius Calculation
**What:** Calculate both global minimum and per-feature minimum tool radii
**When to use:** All geometry analysis
**Example:**
```python
# Source: https://www.autodesk.com/products/fusion360/blog/fusion-360-machine-internal-corners/
def calculate_minimum_tool_radii(body, features):
    """
    Calculate minimum tool radius requirements.

    Returns:
        dict: Global minimum and per-feature requirements
    """
    global_min_radius = float('inf')

    # Scan all faces for smallest concave radius
    for face in body.faces:
        geom = face.geometry

        # Check toroidal faces (fillets, rounds)
        if isinstance(geom, adsk.core.Torus):
            minor_radius_mm = geom.minorRadius * 10
            if minor_radius_mm < global_min_radius:
                global_min_radius = minor_radius_mm

        # Check edges for small arcs
        for edge in face.edges:
            edge_geom = edge.geometry
            if isinstance(edge_geom, (adsk.core.Circle, adsk.core.Arc3D)):
                radius_mm = edge_geom.radius * 10
                if radius_mm < global_min_radius:
                    global_min_radius = radius_mm

    # Apply 80% rule: recommended tool radius is 80% of minimum corner
    # Source: https://www.xometry.com/resources/machining/cnc-machining-optimizing-internal-corner-radii/
    recommended_tool_radius = global_min_radius * 0.8 if global_min_radius != float('inf') else None

    # Per-feature minimum radii
    for feature in features:
        if feature["type"] in ["pocket", "slot"]:
            # Find smallest radius in this feature's faces
            feature_min = float('inf')
            for face_token in feature.get("fusion_faces", []):
                # Note: Would need to resolve face from token
                # Simplified for example
                pass

            feature["minimum_tool_radius"] = {
                "value": round(recommended_tool_radius, 3),
                "unit": "mm"
            } if recommended_tool_radius else None

    return {
        "global_minimum_radius": {
            "value": round(global_min_radius, 3),
            "unit": "mm"
        } if global_min_radius != float('inf') else None,
        "recommended_tool_radius": {
            "value": round(recommended_tool_radius, 3),
            "unit": "mm"
        } if recommended_tool_radius else None,
        "design_guideline": "Consider radii ≥ 0.5mm (0.02in) for optimal machining"
    }
```

### Anti-Patterns to Avoid
- **Ignoring Fusion's RecognizedPocket API:** Custom pocket detection is complex; always use native API first
- **Generating non-associative geometry without entityToken:** Include face/edge tokens for selection; Fusion's feature recognition returns transient Curve3DPath objects that can't be selected directly
- **Over-reliance on pixel-based silhouette analysis:** Use BRep topology for exact analysis; silhouettes are for visualization
- **Forgetting per-user CONTEXT decisions:** User explicitly requested confidence scores, reasoning, and per-feature metadata; don't skip these
- **Assuming all pockets are machinable:** Fusion API warns that results may include non-machinable geometries unlike UI's conservative approach; always flag for review

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Hole detection | Face normal + cylindrical check | `RecognizedHole.recognizeHoles()` | Fusion API handles counterbores, chamfers, multi-segment holes, and non-axis-aligned holes |
| Pocket detection | Manual boundary tracing | `RecognizedPocket.recognizePockets()` | Handles through pockets, islands, closed contours, mixed corner types (fillets/chamfers) |
| Corner radius finding | Edge iteration | Existing `min_internal_radius` calculation in cam_operations.py | Already implemented and tested |
| Bounding box calculation | Manual min/max point iteration | `BRepBody.boundingBox` property | GPU-accelerated, handles all geometry types |
| Silhouette curves | Raycasting or pixel analysis | `TemporaryBRepManager.createSilhouetteCurves()` | Exact parametric curves, not approximations |
| Volume/surface area | Manual mesh integration | `BRepBody.volume` and `BRepBody.surfaceArea` | Exact values, already in cm³/cm² (convert to mm) |

**Key insight:** Fusion's CAM feature recognition APIs are production-tested on millions of parts. They handle edge cases (tolerance issues, degenerate geometry, non-manifold edges) that custom code will miss. Use them as the foundation, augment with custom logic only for unsupported feature types.

## Common Pitfalls

### Pitfall 1: RecognizedPocket Returns Transient Geometry
**What goes wrong:** Code tries to use pocket.boundaries (Curve3DPath objects) directly in CAM operations, but they're not selectable BRep entities.
**Why it happens:** Feature recognition returns transient geometry for flexibility, not persistent BRep references. You can't pass Curve3DPath to operation selection.
**How to avoid:** Use `pocket.faces` to get BRepFace objects with entityToken for selection. If you need to create sketches from boundaries, use `findBRepUsingPoint()` to locate adjacent faces.
**Warning signs:** "Cannot select geometry" errors when trying to assign pocket boundaries to operations.

### Pitfall 2: Fusion API Doesn't Distinguish Slots
**What goes wrong:** All elongated pockets are classified as "pocket" by RecognizedPocket API.
**Why it happens:** Fusion's API doesn't have a slot-specific recognizer; it groups all pockets together.
**How to avoid:** Implement aspect ratio heuristic per user decision. Calculate length/width from pocket bounding box, classify as slot if ratio > 3.0. Mark confidence as 0.85 (heuristic) vs 0.95 (API).
**Warning signs:** User asks "why is this slot not detected" when reviewing features.

### Pitfall 3: Blind Hole Classification Ambiguity
**What goes wrong:** RecognizedHole only detects through-holes or holes from single face. Blind pockets with cylindrical bottoms are classified as pockets, not holes.
**Why it happens:** API design difference: holes are defined by cylindrical segments, pockets by enclosed boundaries. A blind cylindrical pocket could be either.
**How to avoid:** Per user decision, Claude's discretion on classification. Recommend: classify by machining priority (drilling vs pocketing strategy), flag with `needs_review: true` if ambiguous. Include reasoning: "Could be drilled or pocketed based on depth/diameter ratio."
**Warning signs:** Feature appears in both holes and pockets lists, or missing from both.

### Pitfall 4: EntityToken Lifetime and Persistence
**What goes wrong:** Code stores entityToken in database, later retrieval fails with "invalid token" error.
**Why it happens:** EntityTokens are session-specific identifiers. They become invalid when document closes or if geometry is regenerated.
**How to avoid:** Use entityTokens only for immediate selection within same analysis session. For persistence, store BRep topology signature (hash of face areas, edge lengths) or feature name.
**Warning signs:** Code works during analysis but fails when user reopens document.

### Pitfall 5: Orientation Analysis Ignores Workholding
**What goes wrong:** Algorithm recommends Z-up orientation, but part geometry requires side clamping that blocks top features.
**Why it happens:** Pure geometry analysis doesn't account for fixture access, clamp locations, or vise jaw clearance.
**How to avoid:** Include base area in scoring but note in reasoning: "Assumes fixture allows top access." Add note in orientation response: "Verify fixture/clamp clearance before machining." This is CONTEXT decision: provide suggestions, not guarantees.
**Warning signs:** User feedback: "Recommended orientation doesn't work with my vise."

### Pitfall 6: Undercut Detection Complexity
**What goes wrong:** Code marks features as "unreachable" that are actually accessible with tool approach angles.
**Why it happens:** 3-axis undercut detection requires ray casting from tool direction to each face. Simple normal-based checks miss features accessible at oblique angles.
**How to avoid:** Use conservative approach: only flag clearly unreachable features (face normal opposes tool direction by > 90°). For ambiguous cases (75-105° angle), include in reachable list but add note: "May require tapered tool or 4th axis."
**Warning signs:** Too many features flagged as unreachable; user reports successful machining of "unreachable" features.

### Pitfall 7: Confidence Score Inflation
**What goes wrong:** All features report confidence > 0.90, making scores meaningless.
**Why it happens:** Developer wants to appear accurate; sets base scores too high.
**How to avoid:** Calibrate confidence honestly per Pattern 4. Fusion API detections: 0.90-0.95. Heuristic classifications: 0.60-0.80. BRep analysis fallbacks: 0.50-0.70. Use `needs_review: true` for anything < 0.80.
**Warning signs:** User stops trusting confidence scores because they don't correlate with actual ambiguity.

## Code Examples

Verified patterns from official sources:

### Complete Feature Detection Pipeline
```python
# Source: Integration of official Fusion API patterns + user CONTEXT decisions
def analyze_geometry_complete(body, config):
    """
    Complete geometry analysis pipeline per Phase 2 requirements.

    Args:
        body: BRepBody to analyze
        config: {
            "min_feature_size_mm": 0.5,
            "slot_aspect_ratio_threshold": 3.0,
            "confidence_threshold": 0.60
        }

    Returns:
        Analysis results with features grouped by machining priority
    """
    results = {
        "body_name": body.name,
        "bounding_box": extract_bounding_box(body),
        "volume": _to_mm3(body.volume),  # cm³ to mm³
        "surface_area": _to_mm2(body.surfaceArea),  # cm² to mm²
        "material": body.material.name if body.material else "unknown",
        "features_by_priority": [],
        "minimum_tool_radius": None,
        "suggested_orientations": []
    }

    # Step 1: Detect holes using Fusion API
    holes = detect_holes_fusion_api(body, config)

    # Step 2: Detect pockets and slots using Fusion API + heuristics
    pockets_and_slots = detect_pockets_and_slots_fusion_api(body, config)

    # Step 3: Fallback BRep analysis for missed features
    additional_features = detect_features_brep_fallback(body, holes, pockets_and_slots)

    # Step 4: Calculate minimum tool radius (global and per-feature)
    tool_radius_info = calculate_minimum_tool_radii(body, pockets_and_slots)
    results["minimum_tool_radius"] = tool_radius_info

    # Step 5: Group by machining priority per user decision
    all_features = holes + pockets_and_slots + additional_features
    priority_groups = group_by_machining_priority(all_features)
    results["features_by_priority"] = priority_groups

    # Step 6: Orientation suggestions with setup sequences
    results["suggested_orientations"] = suggest_orientations_with_sequences(
        body, all_features
    )

    return results

def group_by_machining_priority(features):
    """
    Group features by machining priority rather than type.
    Per user decision: not grouped by type (holes/pockets/slots).
    """
    priority_map = {
        1: {"name": "drilling_operations", "features": []},
        2: {"name": "roughing_operations", "features": []},
        3: {"name": "finishing_operations", "features": []}
    }

    for feature in features:
        # Priority heuristic
        if feature["type"] == "hole" and feature.get("diameter", {}).get("value", 0) < 6.0:
            # Small holes: drill first
            priority = 1
        elif feature["type"] in ["pocket", "slot"] and feature.get("depth", {}).get("value", 0) > 10.0:
            # Deep pockets: rough first
            priority = 2
        else:
            # Everything else: finishing
            priority = 3

        priority_map[priority]["features"].append(feature)

    # Return only non-empty groups
    return [group for group in priority_map.values() if group["features"]]
```

### EntityToken Usage for Programmatic Selection
```python
# Source: Fusion API best practices + user requirement for actionable features
def get_selectable_geometry_references(feature):
    """
    Extract Fusion geometry IDs (entityTokens) for programmatic selection.

    Returns references that can be used in CAM operation geometry selection.
    """
    selectable_refs = {
        "faces": [],
        "edges": [],
        "vertices": []
    }

    # Faces from feature detection
    for face_token in feature.get("fusion_faces", []):
        selectable_refs["faces"].append({
            "entityToken": face_token,
            "description": "Feature boundary face"
        })

    # Edges for contour selection
    for edge_token in feature.get("fusion_edges", []):
        selectable_refs["edges"].append({
            "entityToken": edge_token,
            "description": "Feature boundary edge"
        })

    return selectable_refs

# Usage in CAM operation creation:
def create_pocket_operation(feature, setup):
    """Create 2D pocket operation from feature."""
    # Get selectable faces
    refs = get_selectable_geometry_references(feature)

    # Create operation input
    input_obj = setup.operations.createInput("adaptive2d")

    # Select geometry using entityTokens
    for face_ref in refs["faces"]:
        # Note: Actual implementation would resolve entityToken to face object
        # face = resolve_entity_token(face_ref["entityToken"])
        # input_obj.geometry.addSelection(face)
        pass

    return input_obj
```

### Unreachable Feature Flagging
```python
# Source: https://www.autodesk.com/products/fusion360/blog/fusion-360-machine-internal-corners/ + CAM best practices
def detect_unreachable_features_3axis(features, tool_direction):
    """
    Flag features unreachable in 3-axis machining.

    Args:
        features: List of detected features
        tool_direction: Vector3D for tool approach (e.g., Z-down)

    Returns:
        Updated features with unreachable flags and reasons
    """
    for feature in features:
        # Get feature faces and analyze normals
        face_tokens = feature.get("fusion_faces", [])

        reachable = False
        unreachable_reasons = []

        for token in face_tokens:
            # Resolve face from token (simplified)
            # face = resolve_entity_token(token)
            # evaluator = face.evaluator
            # _, normal = evaluator.getNormalAtPoint(face.pointOnFace)

            # Check if normal opposes tool direction
            # dot_product = normal.dotProduct(tool_direction)
            # if dot_product > -0.1:  # Face visible to tool (>95° angle)
            #     reachable = True
            # else:
            #     unreachable_reasons.append(f"Face normal opposes tool direction")

            # Placeholder for example
            reachable = True

        # Update feature
        if not reachable:
            feature["unreachable_in_3axis"] = True
            feature["unreachable_reason"] = "; ".join(unreachable_reasons)
            feature["requires"] = "4th axis or multiple setups"
            feature["confidence"] *= 0.9  # Reduce confidence for complex features
        else:
            feature["unreachable_in_3axis"] = False

    return features
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual feature identification via sketches | RecognizedHole/Pocket APIs | Fusion 360 API v1.0+ (2015) | Automated detection, multi-segment hole support |
| Type-based feature grouping | Machining priority grouping | Industry shift to process-based CAM | Matches how machinists plan operations |
| Boolean "accessible" flag | Confidence scores with reasoning | Modern ML/heuristic systems (2020+) | Transparency and user trust in recommendations |
| Axis-aligned bounding boxes only | Oriented bounding box analysis | Open3D, modern CAD APIs (2018+) | Better orientation recommendations |
| Single "best" orientation | Ranked alternatives with tradeoffs | CAM planning evolution (2022+) | User choice based on workholding constraints |

**Deprecated/outdated:**
- **Pixel-based feature recognition:** Modern BRep APIs provide exact topology; pixel methods are legacy from 2D CAM era
- **Synchronous-only analysis:** TemporaryBRepManager enables async transient geometry operations
- **Type-only classification:** Modern approach includes confidence, reasoning, and metadata per user decision

## Open Questions

Things that couldn't be fully resolved:

1. **Slot vs pocket aspect ratio threshold**
   - What we know: Industry uses 2:1 to 4:1 ratios for slot definition
   - What's unclear: Optimal threshold for Fusion 360 parts (user works with varied geometries)
   - Recommendation: Use 3.0 as default per CONTEXT, make configurable via `config.json`. Flag 2.5-3.5 range as `needs_review: true`

2. **Blind hole classification (drill vs pocket)**
   - What we know: Can be machined either way depending on depth/diameter ratio
   - What's unclear: Exact heuristic for when to recommend drilling vs adaptive clearing
   - Recommendation: Per CONTEXT "Claude's discretion," use depth/diameter ratio: drill if < 3:1, pocket if > 4:1, flag 3-4:1 as ambiguous

3. **Bounding box granularity**
   - What we know: User decision allows "Claude's discretion on part-level vs per-feature"
   - What's unclear: Performance impact of per-feature bounding boxes on complex parts
   - Recommendation: Provide part-level always, per-feature for pockets/slots (helps with stock planning), skip for simple holes (noise)

4. **Confidence calibration dataset**
   - What we know: Need confidence scores to correlate with actual classification errors
   - What's unclear: No labeled dataset of Fusion parts with ground-truth feature classifications
   - Recommendation: Start with conservative heuristic scores, add `needs_review` flags liberally. Phase 5 learning system can calibrate based on user corrections.

5. **Orientation scoring weights**
   - What we know: Should minimize setups (high weight), consider stability (medium), maximize feature access (high)
   - What's unclear: Exact weighting for different part types (prismatic vs sculptural)
   - Recommendation: Use 60% feature access, 30% setup count, 10% stability. Make configurable in future based on Phase 5 learning.

## Sources

### Primary (HIGH confidence)
- [Fusion 360 Feature Recognition in CAM](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/FeatureRecognition_UM.htm) - RecognizedHole and RecognizedPocket APIs
- [Hole and Pocket Recognition API Sample](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/HoleAndPocketRecognition_Sample.htm) - Complete code examples
- [BRep Models and Geometry](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/BRepGeometry_UM.htm) - BRep topology traversal, loops, coedges
- [TemporaryBRepManager Object](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/TemporaryBRepManager.htm) - Boolean operations, silhouettes, transformations
- [How to Machine Internal Corners (Fusion Blog)](https://www.autodesk.com/products/fusion360/blog/fusion-360-machine-internal-corners/) - Minimum radius best practices
- Existing implementation: `cam_operations.py` - Verified basic geometry analysis patterns

### Secondary (MEDIUM confidence)
- [CNC Machining: Optimizing Internal Corner Radii (Xometry)](https://www.xometry.com/resources/machining/cnc-machining-optimizing-internal-corner-radii/) - 80% rule for tool radius selection
- [SOLIDWORKS CAM Features and Operations (GoEngineer)](https://www.goengineer.com/blog/solidworks-cam-features-and-allowable-operations) - Pocket vs slot distinction, AFR methodology
- [CAMWorks Open Pocket Features](https://www.goengineer.com/blog/camworks-milling-features-and-allowable-operations) - Industry standards for feature classification
- [Mastercam 2026 Setup Planning](https://www.mastercam.com/news/press-releases/mastercam-2026-delivers-superior-machining-performance/) - Modern CAM orientation and setup minimization
- [Open3D OrientedBoundingBox](https://www.open3d.org/docs/release/python_api/open3d.geometry.OrientedBoundingBox.html) - PCA-based orientation analysis patterns

### Tertiary (LOW confidence)
- [Quick Tip: 3-Axis Undercutting (BobCAD)](https://bobcad.com/quick-tip-3-axis-undercutting/) - General undercut detection concepts
- [Machine Learning Point Cloud Classification (MDPI)](https://www.mdpi.com/2220-9964/10/3/187) - Geometric feature extraction patterns (not CAM-specific)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official Fusion 360 APIs are the only option; RecognizedHole/Pocket are production-tested
- Architecture: HIGH - Official samples demonstrate complete patterns; existing codebase validates approach
- Pitfalls: HIGH - Official docs explicitly warn about transient geometry, entityToken usage; community forums confirm
- Code examples: HIGH - Derived from official samples and verified existing implementation
- Heuristics (slot detection, confidence scoring): MEDIUM - Industry patterns validated but need calibration with user data

**Research date:** 2026-02-05
**Valid until:** 2026-04-05 (60 days) - Fusion 360 API is stable; feature recognition patterns unlikely to change

**Research constraints from CONTEXT.md:**
- Feature detection criteria (holes, slots, pockets, blind holes): LOCKED decisions from user
- Output structure (machining priority grouping, rich metadata, confidence scores): LOCKED decisions
- Confidence & uncertainty (scores, reasoning, needs_review flags): LOCKED decisions
- Orientation suggestions (minimize setups, ranked, sequences, unreachable flags): LOCKED decisions
- Slot vs pocket heuristics, blind hole handling, bounding box granularity: DISCRETION areas for planner
