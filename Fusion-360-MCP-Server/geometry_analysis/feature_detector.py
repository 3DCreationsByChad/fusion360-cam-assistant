"""
Feature Detector for Fusion 360 CAM Assistant.

Uses Fusion 360's RecognizedHole and RecognizedPocket APIs to detect
CAM-relevant features with production-ready accuracy.

Each detected feature includes:
- Geometry data with explicit units (mm)
- Fusion entityTokens for programmatic selection
- Confidence scores and reasoning
- needs_review flag for ambiguous cases
"""

from typing import List, Dict, Any, Optional

# Fusion 360 imports - available when running inside Fusion
try:
    import adsk.core
    import adsk.cam
    FUSION_CAM_AVAILABLE = True
except ImportError:
    FUSION_CAM_AVAILABLE = False


def _to_mm_unit(cm_value: float) -> Dict[str, Any]:
    """
    Convert internal cm value to mm with explicit units.

    Fusion 360 API values are internally in cm. This converts to mm
    and returns an explicit unit object per project convention.

    Args:
        cm_value: Value in centimeters from Fusion API

    Returns:
        Dict with {"value": float, "unit": "mm"}
    """
    return {
        "value": round(cm_value * 10, 3),
        "unit": "mm"
    }


class FeatureDetector:
    """
    Detects CAM-relevant features using Fusion 360's native APIs.

    Provides:
    - detect_holes(): Uses RecognizedHole API for accurate hole detection
    - detect_pockets(): Uses RecognizedPocket API for pocket detection

    Each feature includes fusion_faces with entityTokens for programmatic
    selection in CAM operations.
    """

    def __init__(self):
        """Initialize the feature detector."""
        self._api_available = FUSION_CAM_AVAILABLE

    @property
    def is_available(self) -> bool:
        """Check if Fusion CAM API is available."""
        return self._api_available

    def detect_holes(self, body) -> List[Dict[str, Any]]:
        """
        Detect all holes in a body using Fusion's RecognizedHole API.

        Args:
            body: BRepBody to analyze

        Returns:
            List of hole feature dicts, each containing:
            - type: "hole"
            - diameter: {"value": float, "unit": "mm"}
            - depth: {"value": float, "unit": "mm"} (sum of segment lengths)
            - segment_count: int
            - segments: list of segment info
            - fusion_faces: list of entityTokens for selection
            - confidence: float (0-1)
            - reasoning: str
            - needs_review: bool

        If API fails, returns empty list with error info.
        """
        if not self._api_available:
            return []

        features = []

        try:
            # Use Fusion's RecognizedHole API
            # Source: https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/FeatureRecognition_UM.htm
            holes = adsk.cam.RecognizedHole.recognizeHoles([body])

            if holes is None:
                return []

            for hole in holes:
                try:
                    # Extract segment information
                    segments = []
                    total_depth_cm = 0.0
                    diameter_cm = None

                    # Get segment count
                    segment_count = hole.segmentCount if hasattr(hole, 'segmentCount') else 0

                    # Iterate through segments to get geometry data
                    if hasattr(hole, 'segments'):
                        for segment in hole.segments:
                            seg_info = {
                                "type": self._get_segment_type_name(segment)
                            }

                            # Extract segment length for depth calculation
                            if hasattr(segment, 'length'):
                                seg_length_cm = segment.length
                                total_depth_cm += seg_length_cm
                                seg_info["length"] = _to_mm_unit(seg_length_cm)

                            # Get diameter from cylindrical segments
                            if hasattr(segment, 'diameter') and diameter_cm is None:
                                diameter_cm = segment.diameter
                                seg_info["diameter"] = _to_mm_unit(segment.diameter)

                            # Get taper angle for conical segments
                            if hasattr(segment, 'angle'):
                                seg_info["angle_deg"] = round(segment.angle * 180 / 3.14159, 2)

                            segments.append(seg_info)

                    # Extract entityTokens from hole faces for programmatic selection
                    face_tokens = []
                    if hasattr(hole, 'faces'):
                        for face in hole.faces:
                            if hasattr(face, 'entityToken'):
                                face_tokens.append(face.entityToken)

                    # Calculate confidence based on segment complexity
                    # Simple holes (1 segment): HIGH confidence
                    # Multi-segment holes: reduced confidence
                    # Complex holes (>3 segments): needs review
                    if segment_count <= 1:
                        confidence = 0.95
                        reasoning = "Simple cylindrical hole detected by Fusion API"
                    elif segment_count <= 3:
                        confidence = 0.85
                        reasoning = f"Multi-segment hole ({segment_count} segments) detected by Fusion API"
                    else:
                        confidence = 0.75
                        reasoning = f"Complex hole ({segment_count} segments) - may be counterbore/countersink/step hole"

                    needs_review = segment_count > 3

                    feature = {
                        "type": "hole",
                        "diameter": _to_mm_unit(diameter_cm) if diameter_cm else None,
                        "depth": _to_mm_unit(total_depth_cm) if total_depth_cm > 0 else None,
                        "segment_count": segment_count,
                        "segments": segments if segments else None,
                        "fusion_faces": face_tokens,
                        "confidence": confidence,
                        "reasoning": reasoning,
                        "needs_review": needs_review
                    }

                    features.append(feature)

                except Exception as hole_error:
                    # Log individual hole processing errors but continue
                    features.append({
                        "type": "hole",
                        "error": str(hole_error),
                        "fusion_faces": [],
                        "confidence": 0.0,
                        "reasoning": f"Error processing hole: {str(hole_error)}",
                        "needs_review": True
                    })

        except Exception as e:
            # API call failed - return empty list with error flag
            # This can happen if RecognizedHole is not available in this Fusion version
            return [{
                "type": "hole_detection_error",
                "error": str(e),
                "fusion_faces": [],
                "confidence": 0.0,
                "reasoning": f"RecognizedHole API failed: {str(e)}",
                "needs_review": True
            }]

        return features

    def detect_pockets(
        self,
        body,
        tool_direction=None
    ) -> List[Dict[str, Any]]:
        """
        Detect all pockets in a body using Fusion's RecognizedPocket API.

        Args:
            body: BRepBody to analyze
            tool_direction: Vector3D for tool approach direction.
                           Default: (0, 0, -1) for Z-down machining.

        Returns:
            List of pocket feature dicts, each containing:
            - type: "pocket"
            - depth: {"value": float, "unit": "mm"}
            - is_through: bool
            - dimensions: bounding box info
            - fusion_faces: list of entityTokens for selection
            - confidence: float (0-1)
            - reasoning: str
            - needs_review: bool

        If API fails, returns empty list with error info.
        """
        if not self._api_available:
            return []

        features = []

        try:
            # Default tool direction: Z-down (standard 3-axis vertical machining)
            if tool_direction is None:
                tool_direction = adsk.core.Vector3D.create(0, 0, -1)

            # Use Fusion's RecognizedPocket API
            # Source: https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/HoleAndPocketRecognition_Sample.htm
            pockets = adsk.cam.RecognizedPocket.recognizePockets(body, tool_direction)

            if pockets is None:
                return []

            for pocket in pockets:
                try:
                    # Extract pocket depth
                    depth_cm = None
                    if hasattr(pocket, 'depth'):
                        depth_cm = pocket.depth

                    # Check if pocket goes through the part
                    is_through = False
                    if hasattr(pocket, 'isThrough'):
                        is_through = pocket.isThrough

                    # Extract entityTokens from pocket faces for programmatic selection
                    face_tokens = []
                    min_x = min_y = min_z = float('inf')
                    max_x = max_y = max_z = float('-inf')

                    if hasattr(pocket, 'faces'):
                        for face in pocket.faces:
                            if hasattr(face, 'entityToken'):
                                face_tokens.append(face.entityToken)

                            # Calculate bounding box from face positions
                            try:
                                bbox = face.boundingBox
                                if bbox:
                                    min_x = min(min_x, bbox.minPoint.x)
                                    min_y = min(min_y, bbox.minPoint.y)
                                    min_z = min(min_z, bbox.minPoint.z)
                                    max_x = max(max_x, bbox.maxPoint.x)
                                    max_y = max(max_y, bbox.maxPoint.y)
                                    max_z = max(max_z, bbox.maxPoint.z)
                            except:
                                pass

                    # Build dimensions dict from bounding box
                    dimensions = None
                    if min_x != float('inf'):
                        width_cm = max_x - min_x
                        length_cm = max_y - min_y
                        height_cm = max_z - min_z

                        dimensions = {
                            "width": _to_mm_unit(width_cm),
                            "length": _to_mm_unit(length_cm),
                            "height": _to_mm_unit(height_cm),
                            "bounding_box": {
                                "min_point": {
                                    "x": _to_mm_unit(min_x),
                                    "y": _to_mm_unit(min_y),
                                    "z": _to_mm_unit(min_z)
                                },
                                "max_point": {
                                    "x": _to_mm_unit(max_x),
                                    "y": _to_mm_unit(max_y),
                                    "z": _to_mm_unit(max_z)
                                }
                            }
                        }

                    # Calculate confidence based on detection quality
                    if is_through:
                        confidence = 0.90
                        reasoning = "Through pocket detected by Fusion API"
                    else:
                        confidence = 0.95
                        reasoning = "Closed pocket detected by Fusion API"

                    # Flag ambiguous cases
                    needs_review = False

                    feature = {
                        "type": "pocket",
                        "depth": _to_mm_unit(depth_cm) if depth_cm else None,
                        "is_through": is_through,
                        "dimensions": dimensions,
                        "fusion_faces": face_tokens,
                        "confidence": confidence,
                        "reasoning": reasoning,
                        "needs_review": needs_review
                    }

                    features.append(feature)

                except Exception as pocket_error:
                    # Log individual pocket processing errors but continue
                    features.append({
                        "type": "pocket",
                        "error": str(pocket_error),
                        "fusion_faces": [],
                        "confidence": 0.0,
                        "reasoning": f"Error processing pocket: {str(pocket_error)}",
                        "needs_review": True
                    })

        except Exception as e:
            # API call failed - return empty list with error flag
            # This can happen if RecognizedPocket is not available in this Fusion version
            return [{
                "type": "pocket_detection_error",
                "error": str(e),
                "fusion_faces": [],
                "confidence": 0.0,
                "reasoning": f"RecognizedPocket API failed: {str(e)}",
                "needs_review": True
            }]

        return features

    def _get_segment_type_name(self, segment) -> str:
        """
        Get human-readable name for a hole segment type.

        Hole segments can be: Cylinder, Cone, Flat, Torus
        """
        try:
            if hasattr(segment, 'type'):
                seg_type = segment.type
                # RecognizedHoleSegmentType enum values
                type_names = {
                    0: "Cylinder",
                    1: "Cone",
                    2: "Flat",
                    3: "Torus"
                }
                if hasattr(seg_type, 'value'):
                    return type_names.get(seg_type.value, f"Unknown({seg_type.value})")
                return type_names.get(int(seg_type), str(seg_type))
        except:
            pass
        return "Unknown"
