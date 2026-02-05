# Phase 2: Geometry Analysis

## Goal

Analyze part geometry to extract CAM-relevant information for manufacturing decisions.

## Success Criteria

- [ ] `analyze_geometry_for_cam` returns bounding box, volume, surface area
- [ ] Feature detection identifies pockets, holes, slots
- [ ] Minimum internal radius calculated
- [ ] Orientation suggestions provided with reasoning

## Tasks

### 2.1 Implement analyze_geometry_for_cam

**Input:**
```json
{
  "operation": "analyze_geometry_for_cam",
  "body_names": ["Part1"],
  "analysis_type": "full"
}
```

**Output:**
```json
{
  "bodies_analyzed": 1,
  "results": [{
    "name": "Part1",
    "bounding_box": {"x": 100, "y": 50, "z": 25, "unit": "mm"},
    "volume": 125000,
    "surface_area": 17500,
    "feature_count": 12,
    "min_internal_radius": 3.0,
    "suggested_orientations": [
      {"axis": "Z_UP", "score": 0.9, "reason": "Largest face as base"}
    ]
  }]
}
```

### 2.2 Feature detection heuristics

**Cylindrical features (holes/bosses):**
```python
for face in body.faces:
    geom = face.geometry
    if isinstance(geom, adsk.core.Cylinder):
        radius = geom.radius * 10  # cm to mm
        # Determine if hole (concave) or boss (convex)
        # by checking face normal direction
```

**Planar features (pocket floors):**
```python
if isinstance(geom, adsk.core.Plane):
    area = face.area * 100  # cm² to mm²
    # Large horizontal planes = potential pocket floors
```

**Pocket detection:**
- Find planar faces surrounded by vertical walls
- Calculate depth from top face
- Note corner radii

**Slot detection:**
- Elongated pockets with length >> width
- Often have rounded ends

### 2.3 Orientation scoring

Score each orientation based on:
- **Stability** — larger base face = higher score
- **Feature accessibility** — more features accessible from top = higher score
- **Setup count** — fewer required setups = higher score

```python
def score_orientation(body, axis):
    score = 0.0

    # Stability: area of face perpendicular to axis
    base_area = get_face_area_perpendicular_to(body, axis)
    score += base_area / total_surface_area * 0.4

    # Accessibility: count features reachable from this direction
    accessible = count_accessible_features(body, axis)
    score += accessible / total_features * 0.4

    # Simplicity: prefer common orientations
    if axis == "Z_UP":
        score += 0.2

    return score
```

### 2.4 Material detection

```python
# From body material property
if body.material:
    material_name = body.material.name

# From appearance (visual hint)
if body.appearance:
    appearance_name = body.appearance.name
```

## Dependencies

- Phase 1 complete (cam_operations.py exists)
- Test parts with varied geometry

## Notes

- Face iteration can be slow for complex parts — consider caching
- Fusion uses cm internally, convert to mm for output
- Some features may require BRep analysis for accurate detection

## Estimated Effort

- Basic analysis (bbox, volume): 1 hour
- Feature detection: 2-3 hours
- Orientation scoring: 1-2 hours
- Testing with various parts: 1-2 hours

---

*Phase 2 of Milestone 1: CAM Extension MVP*
