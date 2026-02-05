"""
Orientation Analyzer for Fusion 360 CAM Assistant.

Analyzes part orientations for CAM planning, providing ranked suggestions
with setup sequences optimized for minimal flips/setups.

Per CONTEXT.md decisions:
- Primary optimization goal: minimize setups/flips
- Return all viable orientations, ranked
- Each orientation includes recommended setup/op sequence
- Explicitly flag features that are unreachable in any 3-axis orientation

Per RESEARCH.md Pattern 5 and Open Questions:
- Scoring weights: 60% feature access, 30% setup count, 10% stability
- Make configurable in future based on Phase 5 learning

Exports:
    OrientationAnalyzer: Class for orientation analysis and setup sequence planning
"""

from typing import List, Dict, Any, Optional


class OrientationAnalyzer:
    """
    Analyze part orientations for CAM planning.

    Suggests orientations ranked by minimal setups with setup/flip sequences.
    Per CONTEXT.md: primary optimization goal is minimize setups/flips.

    Usage:
        analyzer = OrientationAnalyzer(detected_features)
        orientations = analyzer.suggest_orientations(body)
    """

    # Scoring weights per RESEARCH.md recommendations
    # Can be made configurable in future phases
    WEIGHTS = {
        "feature_access": 0.60,  # % of features reachable
        "setup_count": 0.30,     # Fewer setups = higher score
        "stability": 0.10        # Base area relative to total
    }

    def __init__(self, features: List[Dict[str, Any]]):
        """
        Initialize the orientation analyzer.

        Args:
            features: List of feature dicts from FeatureDetector
        """
        self.features = features

    def suggest_orientations(self, body) -> List[Dict[str, Any]]:
        """
        Suggest part orientations optimized for minimal setups.

        Analyzes three primary axis orientations (Z_UP, Y_UP, X_UP) and
        scores each based on feature accessibility, setup count, and stability.

        Args:
            body: BRepBody to analyze for bounding box and dimensions

        Returns:
            List of orientation dicts, ranked by score (best first).
            Each orientation contains:
            - axis: "Z_UP", "Y_UP", or "X_UP"
            - score: 0.0-1.0 composite score
            - setup_count: estimated number of setups needed
            - reachable_features: count of accessible features
            - unreachable_features: count of inaccessible features
            - unreachable_feature_list: details of inaccessible features
            - setup_sequence: step-by-step machining sequence
            - base_dimensions: dimensions of base plane
            - reasoning: human-readable explanation
        """
        from .geometry_helpers import analyze_feature_accessibility

        # Get bounding box for dimension calculations
        bbox = body.boundingBox

        orientations = []

        for axis in ["Z_UP", "Y_UP", "X_UP"]:
            # Calculate feature accessibility
            reachable, unreachable = analyze_feature_accessibility(
                self.features, axis
            )

            # Calculate base area for stability scoring
            base_area = self._calculate_base_area(bbox, axis)
            total_area = self._calculate_total_surface_area(bbox)

            # Estimate setup count (1 if all reachable, 2 if some unreachable)
            setup_count = 1 if not unreachable else 2

            # Calculate score using weights
            feature_count = len(self.features)
            feature_ratio = len(reachable) / max(feature_count, 1)
            setup_score = 1.0 / setup_count
            stability_score = base_area / max(total_area, 0.001)

            score = (
                feature_ratio * self.WEIGHTS["feature_access"] +
                setup_score * self.WEIGHTS["setup_count"] +
                stability_score * self.WEIGHTS["stability"]
            )

            # Build setup sequence
            sequence = self._build_setup_sequence(reachable, unreachable, axis)

            # Build unreachable feature list with reasons
            unreachable_list = [
                {
                    "type": f.get("type", "unknown"),
                    "reason": f.get("unreachable_reason", "Opposite face or undercut")
                }
                for f in unreachable
            ]

            orientations.append({
                "axis": axis,
                "score": round(score, 2),
                "setup_count": setup_count,
                "reachable_features": len(reachable),
                "unreachable_features": len(unreachable),
                "unreachable_feature_list": unreachable_list,
                "setup_sequence": sequence,
                "base_dimensions": self._get_base_dimensions(bbox, axis),
                "reasoning": f"{len(reachable)}/{feature_count} features reachable, {setup_count} setup(s) required"
            })

        # Sort by score (highest first)
        orientations.sort(key=lambda x: x["score"], reverse=True)
        return orientations

    def _calculate_base_area(self, bbox, axis: str) -> float:
        """
        Calculate the area of the base face for a given orientation.

        Args:
            bbox: BoundingBox3D from body
            axis: "Z_UP", "Y_UP", or "X_UP"

        Returns:
            Area in cm^2 (Fusion internal units)
        """
        # Get dimensions in cm
        x_dim = bbox.maxPoint.x - bbox.minPoint.x
        y_dim = bbox.maxPoint.y - bbox.minPoint.y
        z_dim = bbox.maxPoint.z - bbox.minPoint.z

        if axis == "Z_UP":
            # Base is XY plane
            return x_dim * y_dim
        elif axis == "Y_UP":
            # Base is XZ plane
            return x_dim * z_dim
        else:  # X_UP
            # Base is YZ plane
            return y_dim * z_dim

    def _calculate_total_surface_area(self, bbox) -> float:
        """
        Calculate approximate total surface area from bounding box.

        Used for stability scoring normalization.

        Args:
            bbox: BoundingBox3D from body

        Returns:
            Approximate surface area in cm^2
        """
        x_dim = bbox.maxPoint.x - bbox.minPoint.x
        y_dim = bbox.maxPoint.y - bbox.minPoint.y
        z_dim = bbox.maxPoint.z - bbox.minPoint.z

        # Sum of all three face pairs (2 * each face area)
        # For scoring, we use half (one of each face type)
        xy_area = x_dim * y_dim
        xz_area = x_dim * z_dim
        yz_area = y_dim * z_dim

        return xy_area + xz_area + yz_area

    def _get_base_dimensions(self, bbox, axis: str) -> Dict[str, Any]:
        """
        Get base plane dimensions with explicit units.

        Args:
            bbox: BoundingBox3D from body
            axis: "Z_UP", "Y_UP", or "X_UP"

        Returns:
            Dict with width, depth, height in mm
        """
        # Get dimensions in mm (convert from cm)
        x_mm = round((bbox.maxPoint.x - bbox.minPoint.x) * 10, 3)
        y_mm = round((bbox.maxPoint.y - bbox.minPoint.y) * 10, 3)
        z_mm = round((bbox.maxPoint.z - bbox.minPoint.z) * 10, 3)

        if axis == "Z_UP":
            return {
                "width": {"value": x_mm, "unit": "mm"},
                "depth": {"value": y_mm, "unit": "mm"},
                "height": {"value": z_mm, "unit": "mm"}
            }
        elif axis == "Y_UP":
            return {
                "width": {"value": x_mm, "unit": "mm"},
                "depth": {"value": z_mm, "unit": "mm"},
                "height": {"value": y_mm, "unit": "mm"}
            }
        else:  # X_UP
            return {
                "width": {"value": y_mm, "unit": "mm"},
                "depth": {"value": z_mm, "unit": "mm"},
                "height": {"value": x_mm, "unit": "mm"}
            }

    def _build_setup_sequence(
        self,
        reachable: List[Dict[str, Any]],
        unreachable: List[Dict[str, Any]],
        axis: str
    ) -> List[Dict[str, Any]]:
        """
        Build step-by-step setup sequence for machining.

        Per CONTEXT.md: Each orientation includes recommended setup/op sequence.

        Args:
            reachable: List of features reachable from primary orientation
            unreachable: List of features requiring flip/additional setup
            axis: Current orientation axis

        Returns:
            List of setup steps with action, description, and feature counts
        """
        sequence = []

        if reachable:
            sequence.append({
                "step": 1,
                "action": "machine_top_features",
                "description": f"Machine {len(reachable)} accessible features from {axis} orientation",
                "feature_count": len(reachable)
            })

        if unreachable:
            sequence.append({
                "step": 2,
                "action": "flip_part",
                "description": "Flip part 180 degrees",
                "requires": "Manual flip or tombstone fixture"
            })
            sequence.append({
                "step": 3,
                "action": "machine_bottom_features",
                "description": f"Machine {len(unreachable)} features from opposite side",
                "feature_count": len(unreachable)
            })

        return sequence
