"""
File: cam_operations.py
Project: MCP-Link Fusion 360 Add-in - CAM Extension
Component: CAM-specific MCP operations for workflow assistance
Created: 2026-02-04

This module extends the Fusion 360 MCP Server with CAM-specific operations:
- get_cam_state: Query current CAM workspace state
- get_tool_library: Query Fusion's tool library
- analyze_geometry_for_cam: Analyze part geometry for manufacturability
- suggest_stock_setup: Recommend stock dimensions and orientation
- suggest_toolpath_strategy: Recommend machining strategies
- record_user_choice: Store user feedback for learning
- get_feedback_stats: View learning statistics
- export_feedback_history: Export feedback data as CSV or JSON
- clear_feedback_history: Reset learning data
- suggest_post_processor: Match machine to post-processor
"""

import json
import os
from typing import Dict, Any, List, Optional

# Fusion 360 imports - these are available when running inside Fusion
try:
    import adsk.core
    import adsk.fusion
    import adsk.cam
    FUSION_AVAILABLE = True
except ImportError:
    FUSION_AVAILABLE = False

# Feature detection and geometry analysis modules
# Provides RecognizedHole/RecognizedPocket wrappers plus orientation analysis
try:
    from .geometry_analysis import (
        FeatureDetector,
        OrientationAnalyzer,
        calculate_minimum_tool_radii
    )
    FEATURE_DETECTOR_AVAILABLE = True
except ImportError:
    FEATURE_DETECTOR_AVAILABLE = False

# Stock suggestions module for stock dimension calculation, cylindrical detection,
# and preference storage via MCP SQLite bridge
try:
    from .stock_suggestions import (
        calculate_stock_dimensions,
        DEFAULT_OFFSETS,
        detect_cylindrical_part,
        get_preference,
        save_preference,
        initialize_schema,
        classify_geometry_type
    )
    STOCK_SUGGESTIONS_AVAILABLE = True
except ImportError:
    STOCK_SUGGESTIONS_AVAILABLE = False

# Toolpath strategy module for operation mapping, tool selection,
# feeds/speeds calculation, and strategy preference storage
try:
    from .toolpath_strategy import (
        get_material_properties,
        calculate_feeds_speeds,
        select_best_tool,
        map_feature_to_operations,
        get_strategy_preference,
        save_strategy_preference,
        initialize_strategy_schema
    )
    TOOLPATH_STRATEGY_AVAILABLE = True
except ImportError:
    TOOLPATH_STRATEGY_AVAILABLE = False

# Feedback learning module for recording user choices and adjusting
# confidence scores based on historical acceptance rates
try:
    from .feedback_learning import (
        initialize_feedback_schema,
        record_feedback,
        get_feedback_statistics,
        export_feedback_history,
        clear_feedback_history,
        get_matching_feedback,
        adjust_confidence_from_feedback,
        should_notify_learning,
        get_conflicting_choices
    )
    FEEDBACK_LEARNING_AVAILABLE = True
except ImportError:
    FEEDBACK_LEARNING_AVAILABLE = False


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_app():
    """Get Fusion 360 application instance."""
    if not FUSION_AVAILABLE:
        raise RuntimeError("Fusion 360 API not available")
    return adsk.core.Application.get()


def _to_mm(cm_value: float) -> Optional[dict]:
    """
    Convert internal cm value to mm with explicit units.

    All Fusion 360 API values are internally in cm. This helper converts
    to mm and returns an explicit unit object per CONTEXT.md decision:
    {"value": X, "unit": "mm"}

    Args:
        cm_value: Value in centimeters from Fusion API

    Returns:
        Dict with value and unit, or None if input is None
    """
    if cm_value is None:
        return None
    return {
        "value": round(cm_value * 10, 3),
        "unit": "mm"
    }


def _extract_stock_info(setup):
    """
    Extract stock information from a CAM setup via parameters.

    The CAM API doesn't expose stock via direct properties like StockModes.
    Instead, stock configuration is accessed through setup.parameters.
    """
    stock_info = {}

    try:
        params = setup.parameters

        # Helper to safely get parameter expression
        def get_param(name, default=None):
            try:
                p = params.itemByName(name)
                if p:
                    return p.expression
            except:
                pass
            return default

        def get_param_float(name, default=0.0):
            try:
                p = params.itemByName(name)
                if p:
                    # Try to get numeric value from expression
                    expr = p.expression
                    try:
                        return float(expr.replace('mm', '').replace('in', '').replace(' ', ''))
                    except:
                        return expr  # Return expression string if can't parse
            except:
                pass
            return default

        # Stock mode
        stock_info['mode'] = get_param('job_stockMode', 'unknown')

        # Stock bounding box (computed values in mm)
        stock_info['bounds'] = {
            'x_low': {"value": get_param_float('stockXLow'), "unit": "mm"},
            'x_high': {"value": get_param_float('stockXHigh'), "unit": "mm"},
            'y_low': {"value": get_param_float('stockYLow'), "unit": "mm"},
            'y_high': {"value": get_param_float('stockYHigh'), "unit": "mm"},
            'z_low': {"value": get_param_float('stockZLow'), "unit": "mm"},
            'z_high': {"value": get_param_float('stockZHigh'), "unit": "mm"},
        }

        # Calculate dimensions from bounds
        bounds = stock_info['bounds']
        try:
            x_low = bounds['x_low']['value'] if isinstance(bounds['x_low']['value'], (int, float)) else 0
            x_high = bounds['x_high']['value'] if isinstance(bounds['x_high']['value'], (int, float)) else 0
            y_low = bounds['y_low']['value'] if isinstance(bounds['y_low']['value'], (int, float)) else 0
            y_high = bounds['y_high']['value'] if isinstance(bounds['y_high']['value'], (int, float)) else 0
            z_low = bounds['z_low']['value'] if isinstance(bounds['z_low']['value'], (int, float)) else 0
            z_high = bounds['z_high']['value'] if isinstance(bounds['z_high']['value'], (int, float)) else 0

            stock_info['dimensions'] = {
                'width': {"value": round(x_high - x_low, 3), "unit": "mm"},
                'depth': {"value": round(y_high - y_low, 3), "unit": "mm"},
                'height': {"value": round(z_high - z_low, 3), "unit": "mm"}
            }
        except:
            pass

        # Stock offsets (for relative/default mode)
        stock_info['offsets'] = {
            'sides': get_param('job_stockOffsetSides'),
            'top': get_param('job_stockOffsetTop'),
            'bottom': get_param('job_stockOffsetBottom'),
        }

        # Fixed stock dimensions (for fixed size box mode)
        stock_info['fixed_size'] = {
            'x': get_param('job_stockFixedX'),
            'y': get_param('job_stockFixedY'),
            'z': get_param('job_stockFixedZ'),
        }

        # Model bounding box (the actual part geometry)
        stock_info['model_bounds'] = {
            'x_low': {"value": get_param_float('surfaceXLow'), "unit": "mm"},
            'x_high': {"value": get_param_float('surfaceXHigh'), "unit": "mm"},
            'y_low': {"value": get_param_float('surfaceYLow'), "unit": "mm"},
            'y_high': {"value": get_param_float('surfaceYHigh'), "unit": "mm"},
            'z_low': {"value": get_param_float('surfaceZLow'), "unit": "mm"},
            'z_high': {"value": get_param_float('surfaceZHigh'), "unit": "mm"},
        }

        # Calculate model dimensions
        model_bounds = stock_info['model_bounds']
        try:
            x_low = model_bounds['x_low']['value'] if isinstance(model_bounds['x_low']['value'], (int, float)) else 0
            x_high = model_bounds['x_high']['value'] if isinstance(model_bounds['x_high']['value'], (int, float)) else 0
            y_low = model_bounds['y_low']['value'] if isinstance(model_bounds['y_low']['value'], (int, float)) else 0
            y_high = model_bounds['y_high']['value'] if isinstance(model_bounds['y_high']['value'], (int, float)) else 0
            z_low = model_bounds['z_low']['value'] if isinstance(model_bounds['z_low']['value'], (int, float)) else 0
            z_high = model_bounds['z_high']['value'] if isinstance(model_bounds['z_high']['value'], (int, float)) else 0

            stock_info['model_dimensions'] = {
                'width': {"value": round(x_high - x_low, 3), "unit": "mm"},
                'depth': {"value": round(y_high - y_low, 3), "unit": "mm"},
                'height': {"value": round(z_high - z_low, 3), "unit": "mm"}
            }
        except:
            pass

        # Cylindrical stock (for turning or rotary)
        stock_info['cylindrical'] = {
            'diameter': get_param('job_stockDiameter'),
            'inner_diameter': get_param('job_stockDiameterInner'),
            'length': get_param('job_stockLength'),
        }

        # Additional useful params
        stock_info['job_type'] = get_param('job_type')
        stock_info['wcs_origin_mode'] = get_param('wcs_origin_mode')
        stock_info['wcs_origin_box_point'] = get_param('wcs_origin_boxPoint')

    except Exception as e:
        stock_info['error'] = str(e)

    return stock_info


def _get_cam_product():
    """Get CAM product from active document, if available."""
    app = _get_app()
    doc = app.activeDocument

    if not doc:
        return None

    # Look for CAM product
    for product in doc.products:
        if product.productType == 'CAMProductType':
            return adsk.cam.CAM.cast(product)

    return None


def _format_response(data: Any, is_error: bool = False) -> Dict:
    """Format response in MCP-compliant format."""
    return {
        "content": [{
            "type": "text",
            "text": json.dumps(data, indent=2) if isinstance(data, (dict, list)) else str(data)
        }],
        "isError": is_error
    }


def _format_error(message: str, details: str = None) -> Dict:
    """Format error response."""
    error_data = {"error": message}
    if details:
        error_data["details"] = details
    return _format_response(error_data, is_error=True)


def _group_by_machining_priority(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Group features by machining priority per CONTEXT.md decision.

    Priority order:
    1. Drilling operations (small holes, spotting)
    2. Roughing operations (deep pockets, large material removal)
    3. Finishing operations (shallow features, fine details)

    Args:
        features: List of feature dicts with type, diameter, depth fields

    Returns:
        List of priority groups (only non-empty groups), each containing:
        - name: operation category name
        - priority: int (1-3)
        - description: human-readable description
        - features: list of features in this priority group
    """
    priority_groups = {
        1: {
            "name": "drilling_operations",
            "priority": 1,
            "description": "Holes suitable for drilling",
            "features": []
        },
        2: {
            "name": "roughing_operations",
            "priority": 2,
            "description": "Features requiring significant material removal",
            "features": []
        },
        3: {
            "name": "finishing_operations",
            "priority": 3,
            "description": "Shallow features and fine details",
            "features": []
        }
    }

    for feature in features:
        # Get feature properties for priority classification
        ftype = feature.get("type", "")

        # Extract diameter value (handles both dict format and raw value)
        diameter = 0
        diameter_data = feature.get("diameter")
        if isinstance(diameter_data, dict):
            diameter = diameter_data.get("value", 0) or 0
        elif isinstance(diameter_data, (int, float)):
            diameter = diameter_data

        # Extract depth value (handles both dict format and raw value)
        depth = 0
        depth_data = feature.get("depth")
        if isinstance(depth_data, dict):
            depth = depth_data.get("value", 0) or 0
        elif isinstance(depth_data, (int, float)):
            depth = depth_data

        # Priority classification heuristics
        if ftype == "hole" and diameter < 12.0:
            # Small holes (< 12mm diameter): suitable for drilling
            priority = 1
        elif ftype in ["pocket", "slot"] and depth > 10.0:
            # Deep pockets/slots (> 10mm depth): require roughing
            priority = 2
        else:
            # Everything else: finishing operations
            # - Large holes (>= 12mm) may need boring/helical milling
            # - Shallow pockets/slots (< 10mm) are finishing
            priority = 3

        priority_groups[priority]["features"].append(feature)

    # Return only non-empty groups, sorted by priority
    return [group for _, group in sorted(priority_groups.items()) if group["features"]]


# =============================================================================
# get_cam_state - Query current CAM workspace state
# =============================================================================

def handle_get_cam_state(arguments: dict) -> dict:
    """
    Get current CAM workspace state.

    Returns information about:
    - Whether CAM workspace exists
    - All setups with stock configuration
    - Operations per setup with status
    - Active setup and post-processor info

    Arguments:
        None required

    Returns:
        {
            "has_cam_workspace": bool,
            "setups": [...],
            "active_setup": str,
            "post_processor": str
        }
    """
    try:
        cam = _get_cam_product()

        if not cam:
            return _format_response({
                "has_cam_workspace": False,
                "message": "No CAM workspace in current document. Create a Setup to begin.",
                "setups": [],
                "active_setup": None
            })

        # Gather setup information
        setups_data = []

        for setup in cam.setups:
            setup_info = {
                "name": setup.name,
                "is_active": getattr(setup, 'isActive', None),  # May be None if API doesn't expose
                "operations": [],
                "stock": None,
                "wcs_origin": None
            }

            # Get stock configuration via parameters (StockModes enum doesn't exist)
            setup_info["stock"] = _extract_stock_info(setup)

            # Get WCS (Work Coordinate System) info per CONTEXT.md decision
            try:
                wcs_info = {}
                params = setup.parameters

                # Z position (stock top/bottom) - most critical for CAM planning
                z_pos = params.itemByName("job_stockZPosition")
                if z_pos:
                    wcs_info["z_origin"] = {
                        "expression": z_pos.expression,
                        "value": _to_mm(z_pos.value.value) if z_pos.value else None
                    }

                # Try to get XY origin if available
                try:
                    wcs_point = params.itemByName("job_wcsOriginPoint")
                    if wcs_point and wcs_point.value:
                        origin_point = wcs_point.value
                        if hasattr(origin_point, 'x'):
                            wcs_info["origin_point"] = {
                                "x": _to_mm(origin_point.x),
                                "y": _to_mm(origin_point.y),
                                "z": _to_mm(origin_point.z)
                            }
                except:
                    pass

                # Try to get orientation info if available
                try:
                    wcs_orientation = params.itemByName("job_wcsOrientation")
                    if wcs_orientation:
                        wcs_info["orientation"] = wcs_orientation.expression
                except:
                    pass

                if wcs_info:
                    setup_info["wcs"] = wcs_info
            except:
                pass

            # Get operations
            for op in setup.operations:
                op_info = {
                    "name": op.name,
                    "type": op.objectType.split("::")[-1] if "::" in op.objectType else op.objectType,
                    "is_valid": op.isValid,
                    "has_error": op.hasError if hasattr(op, 'hasError') else False,
                    "is_suppressed": op.isSuppressed if hasattr(op, 'isSuppressed') else False
                }

                # Try to get strategy type
                try:
                    strategy = op.parameters.itemByName("strategy")
                    if strategy:
                        op_info["strategy"] = strategy.expression
                except:
                    pass

                # Try to get tool info with explicit units
                try:
                    tool = op.tool
                    if tool:
                        op_info["tool"] = {
                            "description": tool.description,
                            "type": tool.type.toString() if hasattr(tool.type, 'toString') else str(tool.type),
                            "diameter": _to_mm(tool.diameter)
                        }
                        # Add flute count if available
                        if hasattr(tool, 'numberOfFlutes'):
                            op_info["tool"]["flutes"] = tool.numberOfFlutes
                except:
                    pass

                setup_info["operations"].append(op_info)

            # Also get folders (operation groups)
            for folder in setup.folders:
                folder_info = {
                    "name": folder.name,
                    "type": "folder",
                    "operations": []
                }
                for op in folder.operations:
                    folder_info["operations"].append({
                        "name": op.name,
                        "type": op.objectType.split("::")[-1] if "::" in op.objectType else op.objectType
                    })
                setup_info["operations"].append(folder_info)

            setups_data.append(setup_info)

        # Note: CAM API doesn't expose activeSetup property
        # Post-processor info would need to be queried per-setup if needed

        result = {
            "has_cam_workspace": True,
            "setup_count": len(setups_data),
            "setups": setups_data,
            "active_setup": None  # CAM API doesn't expose which setup is active
        }

        return _format_response(result)

    except Exception as e:
        import traceback
        return _format_error(f"Failed to get CAM state: {str(e)}", traceback.format_exc())


# =============================================================================
# get_tool_library - Query Fusion's tool library
# =============================================================================

def handle_get_tool_library(arguments: dict) -> dict:
    """
    Query Fusion's tool library.

    Arguments:
        filter (dict, optional):
            type (list): Tool types to include ["endmill", "drill", "ball", etc.]
            diameter_range (list): [min, max] diameter in mm
            material (str): Tool material filter
        library_name (str, optional): Specific library to query
        limit (int, optional): Max tools to return (default 50)

    Returns:
        {
            "tools": [...],
            "total_count": int,
            "libraries": [...]
        }
    """
    try:
        cam = _get_cam_product()

        if not cam:
            return _format_error("No CAM workspace available. Create a Setup first.")

        # Parse filter arguments
        filter_args = arguments.get('filter', {})
        type_filter = filter_args.get('type', [])
        diameter_range = filter_args.get('diameter_range', [0, 1000])
        material_filter = filter_args.get('material', None)
        limit = arguments.get('limit', 50)
        library_name = arguments.get('library_name', None)

        # Normalize type filter to list
        if isinstance(type_filter, str):
            type_filter = [type_filter]

        # Check for include_system_libraries flag (default: False - only document tools)
        include_system = arguments.get('include_system_libraries', False)

        available_libraries = []
        tools_data = []

        # PRIORITY 1: Document tool library (tools embedded in current document)
        # This is where user's working tools typically are
        try:
            doc_lib = cam.documentToolLibrary
            if doc_lib and doc_lib.count > 0:
                available_libraries.append({
                    "name": "Document Tools",
                    "source": "document",
                    "tool_count": doc_lib.count
                })

                # Collect tools from document library
                for i in range(doc_lib.count):
                    if len(tools_data) >= limit:
                        break

                    try:
                        tool = doc_lib.item(i)

                        # Parse tool JSON to get structured data
                        tool_data = {}
                        try:
                            import json
                            tool_json = tool.toJson()
                            tool_data = json.loads(tool_json)
                        except:
                            pass

                        # Extract properties from parsed JSON
                        tool_type_str = tool_data.get("type", "")
                        geometry = tool_data.get("geometry", {})
                        diameter_mm = geometry.get("DC", 0) if geometry else 0

                        # Apply filters
                        if type_filter:
                            type_match = any(t.lower() in tool_type_str.lower() for t in type_filter)
                            if not type_match:
                                continue

                        if diameter_range:
                            if diameter_mm < diameter_range[0] or diameter_mm > diameter_range[1]:
                                continue

                        # Build tool info with explicit units
                        tool_info = {
                            "description": tool.description if hasattr(tool, 'description') else tool_data.get("description", ""),
                            "type": tool_type_str,
                            "diameter": {"value": round(diameter_mm, 3), "unit": "mm"},
                            "library": "Document Tools"
                        }

                        # Add geometry properties (all in mm)
                        if geometry:
                            if "LF" in geometry:
                                tool_info["flute_length"] = {"value": round(geometry["LF"], 3), "unit": "mm"}
                            if "OAL" in geometry:
                                tool_info["overall_length"] = {"value": round(geometry["OAL"], 3), "unit": "mm"}
                            if "SFDM" in geometry:
                                tool_info["shaft_diameter"] = {"value": round(geometry["SFDM"], 3), "unit": "mm"}
                            if "NOF" in geometry:
                                tool_info["flutes"] = geometry["NOF"]

                        # Vendor info
                        vendor = tool_data.get("vendor", "")
                        if vendor:
                            tool_info["vendor"] = vendor

                        tools_data.append(tool_info)

                    except:
                        continue
        except Exception as doc_err:
            pass  # Document library may not exist

        # PRIORITY 2: System libraries (only if requested and we need more tools)
        # Note: System library support can be added later if needed
        # For now, document tools are the primary source

        result = {
            "tools": tools_data,
            "returned_count": len(tools_data),
            "limit": limit,
            "filter_applied": filter_args if filter_args else None,
            "libraries": available_libraries
        }

        return _format_response(result)

    except Exception as e:
        import traceback
        return _format_error(f"Failed to query tool library: {str(e)}", traceback.format_exc())


# =============================================================================
# analyze_geometry_for_cam - Analyze part geometry
# =============================================================================

def handle_analyze_geometry_for_cam(arguments: dict) -> dict:
    """
    Analyze part geometry for CAM manufacturability.

    Arguments:
        body_names (list, optional): Specific bodies to analyze
        analysis_type (str): "full", "quick", or "features_only"

    Returns:
        {
            "bodies_analyzed": int,
            "results": [{
                "name": str,
                "bounding_box": {...},
                "volume": float,
                "surface_area": float,
                "features": [...],
                "min_internal_radius": float,
                "suggested_orientations": [...]
            }]
        }
    """
    try:
        app = _get_app()
        design = adsk.fusion.Design.cast(app.activeProduct)

        if not design:
            return _format_error("No active design. Open a design document first.")

        root_comp = design.rootComponent
        body_names = arguments.get('body_names', [])
        analysis_type = arguments.get('analysis_type', 'full')

        # Get bodies to analyze
        bodies = []
        if body_names:
            for body in root_comp.bRepBodies:
                if body.name in body_names:
                    bodies.append(body)
        else:
            bodies = list(root_comp.bRepBodies)

        if not bodies:
            return _format_error("No bodies found to analyze.")

        results = []

        for body in bodies:
            try:
                bbox = body.boundingBox

                # Basic measurements (convert cm to mm)
                body_result = {
                    "name": body.name,
                    "bounding_box": {
                        "x": round((bbox.maxPoint.x - bbox.minPoint.x) * 10, 2),
                        "y": round((bbox.maxPoint.y - bbox.minPoint.y) * 10, 2),
                        "z": round((bbox.maxPoint.z - bbox.minPoint.z) * 10, 2),
                        "min_point": {
                            "x": round(bbox.minPoint.x * 10, 2),
                            "y": round(bbox.minPoint.y * 10, 2),
                            "z": round(bbox.minPoint.z * 10, 2)
                        },
                        "max_point": {
                            "x": round(bbox.maxPoint.x * 10, 2),
                            "y": round(bbox.maxPoint.y * 10, 2),
                            "z": round(bbox.maxPoint.z * 10, 2)
                        },
                        "unit": "mm"
                    },
                    "volume_mm3": round(body.volume * 1000, 2),  # cm³ to mm³
                    "surface_area_mm2": round(body.surfaceArea * 100, 2),  # cm² to mm²
                }

                # Material info if available
                if body.material:
                    body_result["material"] = body.material.name
                if body.appearance:
                    body_result["appearance"] = body.appearance.name

                # Feature analysis (if not quick mode)
                if analysis_type in ['full', 'features_only']:
                    features = []
                    min_radius = float('inf')
                    face_count = 0
                    planar_count = 0
                    cylindrical_count = 0

                    for face in body.faces:
                        face_count += 1
                        geom = face.geometry

                        # Detect cylindrical features (holes, bosses)
                        if isinstance(geom, adsk.core.Cylinder):
                            radius_mm = geom.radius * 10
                            if radius_mm < min_radius:
                                min_radius = radius_mm
                            cylindrical_count += 1

                            # Determine if it's likely a hole (internal) or boss (external)
                            # by checking the face normal direction relative to axis
                            features.append({
                                "type": "cylindrical",
                                "radius_mm": round(radius_mm, 3),
                                "diameter_mm": round(radius_mm * 2, 3)
                            })

                        # Detect planar faces
                        elif isinstance(geom, adsk.core.Plane):
                            planar_count += 1
                            area_mm2 = face.area * 100

                            # Only record significant planar faces
                            if area_mm2 > 10:
                                # Get face normal to determine orientation
                                evaluator = face.evaluator
                                _, normal = evaluator.getNormalAtPoint(face.pointOnFace)

                                features.append({
                                    "type": "planar",
                                    "area_mm2": round(area_mm2, 2),
                                    "normal": {
                                        "x": round(normal.x, 3),
                                        "y": round(normal.y, 3),
                                        "z": round(normal.z, 3)
                                    }
                                })

                        # Detect conical features
                        elif isinstance(geom, adsk.core.Cone):
                            features.append({
                                "type": "conical",
                                "half_angle": round(geom.halfAngle * 180 / 3.14159, 2)
                            })

                        # Detect spherical features
                        elif isinstance(geom, adsk.core.Sphere):
                            features.append({
                                "type": "spherical",
                                "radius_mm": round(geom.radius * 10, 3)
                            })

                        # Detect toroidal features (fillets, rounds)
                        elif isinstance(geom, adsk.core.Torus):
                            minor_radius = geom.minorRadius * 10
                            if minor_radius < min_radius:
                                min_radius = minor_radius
                            features.append({
                                "type": "toroidal",
                                "minor_radius_mm": round(minor_radius, 3),
                                "major_radius_mm": round(geom.majorRadius * 10, 3)
                            })

                    body_result["face_count"] = face_count
                    body_result["feature_summary"] = {
                        "planar_faces": planar_count,
                        "cylindrical_faces": cylindrical_count,
                        "total_features_detected": len(features)
                    }

                    # Keep face-based features for backward compatibility
                    body_result["face_features"] = features[:20]
                    if len(features) > 20:
                        body_result["face_features_truncated"] = True
                        body_result["total_face_features"] = len(features)

                    body_result["min_internal_radius_mm"] = round(min_radius, 3) if min_radius != float('inf') else None

                    # Use FeatureDetector for production-ready feature recognition
                    # Provides holes and pockets/slots from Fusion's RecognizedHole/RecognizedPocket APIs
                    if FEATURE_DETECTOR_AVAILABLE and analysis_type == 'full':
                        try:
                            detector = FeatureDetector()
                            if detector.is_available:
                                # Detect holes using Fusion's RecognizedHole API
                                detected_holes = detector.detect_holes(body)

                                # Detect pockets/slots using Fusion's RecognizedPocket API
                                # Note: slots are classified by aspect_ratio > 3.0
                                detected_pockets = detector.detect_pockets(body)

                                # Combine all recognized features for priority grouping
                                all_recognized_features = detected_holes + detected_pockets

                                # Count features by type (holes, pockets, slots)
                                hole_count = len([f for f in detected_holes if f.get("type") == "hole"])
                                pocket_count = len([f for f in detected_pockets if f.get("type") == "pocket"])
                                slot_count = len([f for f in detected_pockets if f.get("type") == "slot"])

                                # Group features by machining priority (drilling, roughing, finishing)
                                features_by_priority = _group_by_machining_priority(all_recognized_features)

                                # Add recognized features to result
                                body_result["recognized_features"] = {
                                    "holes": detected_holes,
                                    "pockets": [p for p in detected_pockets if p.get("type") == "pocket"],
                                    "slots": [s for s in detected_pockets if s.get("type") == "slot"],
                                    "total_holes": hole_count,
                                    "total_pockets": pocket_count,
                                    "total_slots": slot_count
                                }

                                # Add priority-grouped features for CAM planning
                                body_result["features_by_priority"] = features_by_priority

                                # Add feature count summary
                                body_result["feature_count"] = {
                                    "holes": hole_count,
                                    "pockets": pocket_count,
                                    "slots": slot_count,
                                    "total": len(all_recognized_features)
                                }

                                body_result["feature_detection_source"] = "fusion_api"

                                # Enhanced orientation analysis with setup sequences
                                # Uses OrientationAnalyzer when features are available
                                if all_recognized_features:
                                    try:
                                        analyzer = OrientationAnalyzer(all_recognized_features)
                                        enhanced_orientations = analyzer.suggest_orientations(body)
                                        body_result["suggested_orientations"] = enhanced_orientations
                                        body_result["orientation_analysis_source"] = "feature_based"
                                    except Exception as orient_error:
                                        body_result["orientation_analysis_error"] = str(orient_error)
                                        body_result["orientation_analysis_source"] = "bounding_box"

                                # Minimum tool radius calculation with 80% rule
                                try:
                                    tool_radius_info = calculate_minimum_tool_radii(
                                        body, all_recognized_features
                                    )
                                    body_result["minimum_tool_radius"] = tool_radius_info
                                except Exception as radius_error:
                                    body_result["minimum_tool_radius"] = {
                                        "error": str(radius_error),
                                        "global_minimum_radius": None,
                                        "recommended_tool_radius": None
                                    }
                            else:
                                body_result["feature_detection_source"] = "face_analysis"
                                body_result["recognized_features"] = None
                                body_result["features_by_priority"] = None
                                body_result["feature_count"] = None
                        except Exception as detector_error:
                            # Fallback to face analysis if detector fails
                            body_result["feature_detection_source"] = "face_analysis"
                            body_result["recognized_features"] = None
                            body_result["features_by_priority"] = None
                            body_result["feature_count"] = None
                            body_result["feature_detector_error"] = str(detector_error)
                    else:
                        body_result["feature_detection_source"] = "face_analysis"
                        body_result["recognized_features"] = None
                        body_result["features_by_priority"] = None
                        body_result["feature_count"] = None

                # Fallback orientation suggestions based on bounding box
                # Only used if enhanced orientation analysis wasn't performed
                if "suggested_orientations" not in body_result:
                    dims = body_result["bounding_box"]
                    orientations = []

                    # Calculate face areas for stability scoring
                    xy_area = dims["x"] * dims["y"]
                    xz_area = dims["x"] * dims["z"]
                    yz_area = dims["y"] * dims["z"]
                    total_area = xy_area + xz_area + yz_area

                    if total_area > 0:
                        # Z-up: XY plane as base
                        z_up_score = xy_area / total_area * 0.8 + 0.2
                        orientations.append({
                            "axis": "Z_UP",
                            "score": round(z_up_score, 2),
                            "reason": "XY plane as base" + (" (largest face)" if xy_area >= xz_area and xy_area >= yz_area else ""),
                            "base_dimensions": f"{dims['x']}x{dims['y']}mm",
                            "height": f"{dims['z']}mm"
                        })

                        # Y-up: XZ plane as base
                        y_up_score = xz_area / total_area * 0.8 + 0.1
                        orientations.append({
                            "axis": "Y_UP",
                            "score": round(y_up_score, 2),
                            "reason": "XZ plane as base" + (" (largest face)" if xz_area > xy_area and xz_area >= yz_area else ""),
                            "base_dimensions": f"{dims['x']}x{dims['z']}mm",
                            "height": f"{dims['y']}mm"
                        })

                        # X-up: YZ plane as base
                        x_up_score = yz_area / total_area * 0.8
                        orientations.append({
                            "axis": "X_UP",
                            "score": round(x_up_score, 2),
                            "reason": "YZ plane as base" + (" (largest face)" if yz_area > xy_area and yz_area > xz_area else ""),
                            "base_dimensions": f"{dims['y']}x{dims['z']}mm",
                            "height": f"{dims['x']}mm"
                        })

                    # Sort by score
                    orientations.sort(key=lambda x: x["score"], reverse=True)
                    body_result["suggested_orientations"] = orientations
                    body_result["orientation_analysis_source"] = "bounding_box"

                results.append(body_result)

            except Exception as body_error:
                results.append({
                    "name": body.name,
                    "error": str(body_error)
                })

        return _format_response({
            "bodies_analyzed": len(results),
            "analysis_type": analysis_type,
            "results": results
        })

    except Exception as e:
        import traceback
        return _format_error(f"Failed to analyze geometry: {str(e)}", traceback.format_exc())


# =============================================================================
# suggest_stock_setup - Suggest stock dimensions and orientation
# =============================================================================

def handle_suggest_stock_setup(arguments: dict) -> dict:
    """
    Suggest stock setup based on geometry analysis.

    Main MCP operation that calculates stock dimensions from part geometry,
    recommends orientation, detects cylindrical parts, and manages user
    preferences. Implements interactive prompting per CONTEXT.md when
    preferences don't exist or orientation confidence is low.

    Arguments:
        body_name (str, optional): Specific body to analyze (default: first body)
        material (str, optional): Material name for preference lookup
        use_defaults (bool): If True, skip preference check and use defaults
        save_as_preference (bool): If True, save current values as new preference
        custom_offsets (dict): Override offsets with {"xy_mm": X, "z_mm": Y}
        round_to_standard (bool): Round to standard stock sizes (default: True)
        selected_orientation (str): User's orientation choice when prompted

    Returns:
        One of three status responses:

        "success": Full stock suggestion returned
            {
                "status": "success",
                "stock_dimensions": {...},
                "recommended_shape": "rectangular" | "round",
                "orientation": {...},
                "setup_sequence": [...],
                "offsets_applied": {...},
                "source": "from: user_preference" | "from: default",
                ...
            }

        "preference_needed": User should establish preference first
            {
                "status": "preference_needed",
                "message": "No stored preference for {material} + {geometry_type}...",
                "suggested_defaults": {...},
                "how_to_proceed": "..."
            }

        "orientation_choice_needed": Low confidence, user should select orientation
            {
                "status": "orientation_choice_needed",
                "message": "Multiple valid orientations...",
                "alternatives": [...],
                "how_to_proceed": "..."
            }
    """
    try:
        # Check module availability
        if not STOCK_SUGGESTIONS_AVAILABLE:
            return _format_error(
                "Stock suggestions module not available",
                "Import failed for stock_suggestions module"
            )

        if not FUSION_AVAILABLE:
            return _format_error("Fusion 360 API not available")

        app = _get_app()
        design = adsk.fusion.Design.cast(app.activeProduct)

        if not design:
            return _format_error("No active design. Open a design document first.")

        root_comp = design.rootComponent

        # Get body to analyze
        body_name = arguments.get('body_name')
        body = None

        if body_name:
            # Find specific body by name
            for b in root_comp.bRepBodies:
                if b.name == body_name:
                    body = b
                    break
            if not body:
                return _format_error(f"Body '{body_name}' not found in design")
        else:
            # Use first body
            if root_comp.bRepBodies.count > 0:
                body = root_comp.bRepBodies.item(0)
            else:
                return _format_error("No bodies found in design")

        # Detect unit system from design
        units_mgr = design.unitsManager
        default_units = units_mgr.defaultLengthUnits
        unit_system = "imperial" if "in" in default_units.lower() else "metric"

        # Get material from body or arguments
        material = arguments.get('material')
        if not material:
            if body.material:
                material = body.material.name
            else:
                material = "unknown"

        # Parse other arguments
        use_defaults = arguments.get('use_defaults', False)
        save_as_pref = arguments.get('save_as_preference', False)
        custom_offsets = arguments.get('custom_offsets')
        round_to_standard = arguments.get('round_to_standard', True)
        selected_orientation = arguments.get('selected_orientation')

        # ---------------------------------------------------------------------
        # Run geometry analysis to get features and orientations
        # ---------------------------------------------------------------------
        analysis_result = handle_analyze_geometry_for_cam({
            'body_names': [body.name],
            'analysis_type': 'full'
        })

        # Extract body result from analysis
        analysis_data = None
        try:
            content = analysis_result.get('content', [])
            if content and len(content) > 0:
                analysis_data = json.loads(content[0].get('text', '{}'))
        except Exception:
            pass

        if not analysis_data or analysis_data.get('error'):
            return _format_error(
                "Geometry analysis failed",
                str(analysis_data.get('error') if analysis_data else 'Unknown error')
            )

        body_result = analysis_data.get('results', [{}])[0]

        # Get recognized features for classification
        recognized_features = body_result.get('recognized_features', {})
        all_features = []
        if recognized_features:
            all_features.extend(recognized_features.get('holes', []))
            all_features.extend(recognized_features.get('pockets', []))
            all_features.extend(recognized_features.get('slots', []))

        # Classify geometry type for preference keying
        geometry_type = classify_geometry_type(all_features)

        # ---------------------------------------------------------------------
        # Preference check (per CONTEXT.md)
        # ---------------------------------------------------------------------
        # Define MCP call function placeholder
        # In production, this would be passed from the MCP bridge
        mcp_call_func = arguments.get('_mcp_call_func')

        preference = None
        if mcp_call_func and not use_defaults:
            # Initialize schema (safe to call multiple times)
            initialize_schema(mcp_call_func)

            # Try to get stored preference
            preference = get_preference(material, geometry_type, mcp_call_func)

            # If no preference exists, prompt user
            if preference is None:
                return _format_response({
                    "status": "preference_needed",
                    "message": f"No stored preference for '{material}' + '{geometry_type}'. "
                               "Please establish a preference for this combination, or use use_defaults=true.",
                    "material": material,
                    "geometry_type": geometry_type,
                    "suggested_defaults": {
                        "offsets_xy_mm": DEFAULT_OFFSETS["xy_mm"],
                        "offsets_z_mm": DEFAULT_OFFSETS["z_mm"],
                        "stock_shape": "rectangular"
                    },
                    "how_to_proceed": (
                        "Call suggest_stock_setup with use_defaults=true to proceed with defaults, "
                        "or with save_as_preference=true to save current values as preference."
                    )
                })

        # ---------------------------------------------------------------------
        # Learning integration: adjust confidence from feedback history
        # ---------------------------------------------------------------------
        learning_metadata = None
        if FEEDBACK_LEARNING_AVAILABLE and mcp_call_func:
            try:
                initialize_feedback_schema(mcp_call_func)
                feedback_history = get_matching_feedback(
                    operation_type="stock_setup",
                    material=material,
                    geometry_type=geometry_type,
                    limit=50,
                    mcp_call_func=mcp_call_func
                )
                if feedback_history:
                    base_confidence = 0.8  # Default stock suggestion confidence
                    adjusted_confidence, learning_source = adjust_confidence_from_feedback(
                        base_confidence=base_confidence,
                        feedback_history=feedback_history
                    )
                    learning_metadata = {
                        "sample_count": len(feedback_history),
                        "adjusted_confidence": adjusted_confidence,
                        "source": learning_source
                    }
                    # Override source tag if learning has kicked in
                    if learning_source.startswith("user_preference"):
                        source = f"from: {learning_source}"
                    # First-time learning notification
                    if should_notify_learning(feedback_history):
                        learning_metadata["notification"] = (
                            f"I noticed patterns in your preferences for {material}. "
                            "Future suggestions will reflect what you've chosen before."
                        )
            except Exception:
                pass  # Learning is non-critical, don't break suggestions

        # ---------------------------------------------------------------------
        # Determine offsets to use
        # Priority: custom_offsets > preference > DEFAULT_OFFSETS
        # ---------------------------------------------------------------------
        if custom_offsets:
            offsets = {
                "xy_mm": custom_offsets.get("xy_mm", DEFAULT_OFFSETS["xy_mm"]),
                "z_mm": custom_offsets.get("z_mm", DEFAULT_OFFSETS["z_mm"])
            }
            source = "from: custom_offsets"
        elif preference:
            offsets = {
                "xy_mm": preference.get("offsets_xy_mm", DEFAULT_OFFSETS["xy_mm"]),
                "z_mm": preference.get("offsets_z_mm", DEFAULT_OFFSETS["z_mm"])
            }
            source = preference.get("source", "from: user_preference")
        else:
            offsets = DEFAULT_OFFSETS.copy()
            source = "from: default"

        # ---------------------------------------------------------------------
        # Calculate stock dimensions
        # ---------------------------------------------------------------------
        bbox = body.boundingBox
        stock_dims = calculate_stock_dimensions(
            bbox=bbox,
            offsets=offsets,
            round_to_standard=round_to_standard,
            unit_system=unit_system
        )

        # ---------------------------------------------------------------------
        # Get orientation analysis
        # ---------------------------------------------------------------------
        orientations = body_result.get('suggested_orientations', [])

        if not orientations:
            orientations = [{
                "axis": "Z_UP",
                "score": 0.5,
                "reasoning": "Default orientation - no analysis available",
                "setup_sequence": ["Single setup with Z-up orientation"]
            }]

        best_orientation = orientations[0] if orientations else None
        best_score = best_orientation.get('score', 0) if best_orientation else 0

        # ---------------------------------------------------------------------
        # Orientation confidence check (per CONTEXT.md)
        # If best score < 0.7 and no selection provided, prompt user
        # ---------------------------------------------------------------------
        if best_score < 0.7 and not selected_orientation:
            # Find close alternatives (within 15% of best score)
            alternatives = []
            for orient in orientations:
                score_diff = best_score - orient.get('score', 0)
                if score_diff < 0.15:  # Within 15%
                    alternatives.append({
                        "axis": orient.get("axis"),
                        "score": orient.get("score"),
                        "reasoning": orient.get("reasoning"),
                        "setup_sequence": orient.get("setup_sequence", [])
                    })

            return _format_response({
                "status": "orientation_choice_needed",
                "message": f"Multiple valid orientations with similar scores. "
                           f"Best score: {best_score:.2f} (below 0.70 threshold).",
                "best_orientation": alternatives[0] if alternatives else None,
                "alternatives": alternatives,
                "how_to_proceed": (
                    "Call suggest_stock_setup with selected_orientation='X_UP'|'Y_UP'|'Z_UP' "
                    "to choose an orientation."
                )
            })

        # If user selected an orientation, find and use it
        chosen_orientation = best_orientation
        if selected_orientation:
            for orient in orientations:
                if orient.get("axis", "").upper() == selected_orientation.upper():
                    chosen_orientation = orient
                    break

        # Extract orientation details
        orientation_axis = chosen_orientation.get("axis", "Z_UP") if chosen_orientation else "Z_UP"
        orientation_score = chosen_orientation.get("score", 0.5) if chosen_orientation else 0.5
        orientation_reasoning = chosen_orientation.get("reasoning", "") if chosen_orientation else ""
        setup_sequence = chosen_orientation.get("setup_sequence", []) if chosen_orientation else []

        # Ensure setup_sequence is always present (even for single-setup)
        if not setup_sequence:
            setup_sequence = [f"Single setup with {orientation_axis} orientation"]

        # Find close alternatives for response (within 15% of best)
        close_alternatives = []
        for orient in orientations[1:]:  # Skip best orientation
            if best_score > 0:
                score_diff = best_score - orient.get('score', 0)
                if score_diff < 0.15:  # Within 15%
                    close_alternatives.append({
                        "axis": orient.get("axis"),
                        "score": orient.get("score"),
                        "reasoning": orient.get("reasoning")
                    })

        # ---------------------------------------------------------------------
        # Detect cylindrical part
        # ---------------------------------------------------------------------
        cylindrical = detect_cylindrical_part(body, all_features)

        # Build round stock dimensions if cylindrical
        round_stock = None
        if cylindrical.get("is_cylindrical"):
            # Calculate round stock dimensions with offset
            enclosing_dia = cylindrical.get("enclosing_diameter_mm", 0)
            round_dia_with_offset = enclosing_dia + (2 * offsets["xy_mm"])

            # Get the length along the cylinder axis
            bbox_dims = body_result.get("bounding_box", {})
            axis = cylindrical.get("cylinder_axis", "Z")

            if axis == "X":
                length = bbox_dims.get("x", 0)
            elif axis == "Y":
                length = bbox_dims.get("y", 0)
            else:  # Z
                length = bbox_dims.get("z", 0)

            length_with_offset = length + offsets["z_mm"]

            round_stock = {
                "diameter": {"value": round(round_dia_with_offset, 1), "unit": "mm"},
                "length": {"value": round(length_with_offset, 1), "unit": "mm"},
                "cylinder_axis": axis
            }

        # ---------------------------------------------------------------------
        # Save preference if requested
        # ---------------------------------------------------------------------
        if save_as_pref and mcp_call_func:
            save_preference(
                material=material,
                geometry_type=geometry_type,
                preference_dict={
                    "offsets_xy_mm": offsets["xy_mm"],
                    "offsets_z_mm": offsets["z_mm"],
                    "preferred_orientation": orientation_axis,
                    "stock_shape": "round" if cylindrical.get("is_cylindrical") else "rectangular"
                },
                mcp_call_func=mcp_call_func
            )

        # ---------------------------------------------------------------------
        # Build success response
        # ---------------------------------------------------------------------
        response = {
            "status": "success",
            "stock_dimensions": {
                "rectangular": {
                    "width": stock_dims["width"],
                    "depth": stock_dims["depth"],
                    "height": stock_dims["height"]
                },
                "round": round_stock
            },
            "recommended_shape": "round" if cylindrical.get("is_cylindrical") else "rectangular",
            "shape_trade_offs": cylindrical.get("trade_offs"),
            "orientation": {
                "recommended": orientation_axis,
                "score": orientation_score,
                "reasoning": orientation_reasoning,
                "alternatives": close_alternatives if close_alternatives else []
            },
            "setup_sequence": setup_sequence,
            "offsets_applied": offsets,
            "source": source,
            "material": material,
            "geometry_type": geometry_type,
            "unit_system": unit_system,
            "raw_dimensions": stock_dims.get("raw_dimensions"),
            "rounded_to_standard": stock_dims.get("rounded_to_standard"),
            "learning_metadata": learning_metadata
        }

        return _format_response(response)

    except Exception as e:
        import traceback
        return _format_error(f"Failed to suggest stock setup: {str(e)}", traceback.format_exc())


# =============================================================================
# suggest_toolpath_strategy - Suggest CAM operations for features
# =============================================================================

def handle_suggest_toolpath_strategy(arguments: dict) -> dict:
    """
    Suggest toolpath strategies based on feature analysis.

    Main MCP operation that analyzes part features, recommends CAM operations
    (roughing/finishing), selects tools, and calculates cutting parameters.
    Implements strategy preference storage via MCP SQLite bridge.

    Arguments:
        body_name (str, optional): Specific body to analyze (default: first body)
        material (str, optional): Material name for SFM lookup (default: from body or "aluminum")
        use_defaults (bool): Skip preference check, use default rules (default: False)
        save_as_preference (bool): Save results as new preferences (default: False)
        is_carbide (bool): Whether tools are carbide (default: True)

    Returns:
        One of two status responses:

        "success": Full strategy suggestions returned
            {
                "status": "success",
                "material": str,
                "is_carbide": bool,
                "feature_count": int,
                "suggestions": [
                    {
                        "feature": {...},
                        "roughing": {...},
                        "finishing": {...},
                        "recommended_tool": {...},
                        "cutting_parameters": {...}
                    }
                ],
                "processing_order": str,
                "source": str,
                "note": str
            }

        "no_features": No machinable features detected
            {
                "status": "no_features",
                "message": str,
                "body_name": str
            }
    """
    try:
        # Check module availability
        if not TOOLPATH_STRATEGY_AVAILABLE:
            return _format_error(
                "Toolpath strategy module not available",
                "Import failed for toolpath_strategy module"
            )

        if not FUSION_AVAILABLE:
            return _format_error("Fusion 360 API not available")

        app = _get_app()
        design = adsk.fusion.Design.cast(app.activeProduct)

        if not design:
            return _format_error("No active design. Open a design document first.")

        root_comp = design.rootComponent

        # Get body to analyze
        body_name = arguments.get('body_name')
        body = None

        if body_name:
            # Find specific body by name
            for b in root_comp.bRepBodies:
                if b.name == body_name:
                    body = b
                    break
            if not body:
                return _format_error(f"Body '{body_name}' not found in design")
        else:
            # Use first body
            if root_comp.bRepBodies.count > 0:
                body = root_comp.bRepBodies.item(0)
            else:
                return _format_error("No bodies found in design")

        # Get material from body or arguments
        material = arguments.get('material')
        if not material:
            if body.material:
                material = body.material.name
            else:
                material = "aluminum"

        # Parse other arguments
        use_defaults = arguments.get('use_defaults', False)
        save_as_pref = arguments.get('save_as_preference', False)
        is_carbide = arguments.get('is_carbide', True)

        # ---------------------------------------------------------------------
        # Run geometry analysis to get features
        # ---------------------------------------------------------------------
        analysis_result = handle_analyze_geometry_for_cam({
            'body_names': [body.name],
            'analysis_type': 'full'
        })

        # Extract body result from analysis
        analysis_data = None
        try:
            content = analysis_result.get('content', [])
            if content and len(content) > 0:
                analysis_data = json.loads(content[0].get('text', '{}'))
        except Exception:
            pass

        if not analysis_data or analysis_data.get('error'):
            return _format_error(
                "Geometry analysis failed",
                str(analysis_data.get('error') if analysis_data else 'Unknown error')
            )

        body_result = analysis_data.get('results', [{}])[0]

        # Get recognized features
        recognized_features = body_result.get('recognized_features', {})

        # Build feature list with priority ordering
        features_by_priority = []
        all_features = []

        # Add features in priority order: holes (drilling) first, then pockets, then slots
        if recognized_features.get('holes'):
            for hole in recognized_features['holes']:
                hole['type'] = 'hole'
                hole['priority'] = 1  # Drilling first
                features_by_priority.append(hole)
                all_features.append(hole)

        if recognized_features.get('pockets'):
            for pocket in recognized_features['pockets']:
                pocket['type'] = 'pocket'
                pocket['priority'] = 2  # Roughing second
                features_by_priority.append(pocket)
                all_features.append(pocket)

        if recognized_features.get('slots'):
            for slot in recognized_features['slots']:
                slot['type'] = 'slot'
                slot['priority'] = 2  # Roughing second (same as pockets)
                features_by_priority.append(slot)
                all_features.append(slot)

        # Classify geometry type for learning context
        geometry_type = classify_geometry_type(all_features)

        # If no features detected
        if not features_by_priority:
            # Build helpful diagnostic info about what WAS found
            face_summary = body_result.get("feature_summary", {})
            face_features = body_result.get("face_features", [])

            # Count geometry types found
            cylindrical_count = face_summary.get("cylindrical_faces", 0)
            planar_count = face_summary.get("planar_faces", 0)

            # Identify what kinds of non-recognized geometry exists
            geometry_found = []
            if cylindrical_count > 0:
                geometry_found.append(f"{cylindrical_count} cylindrical faces")
            if planar_count > 0:
                geometry_found.append(f"{planar_count} planar faces")

            # Check for complex surfaces (NURBS, splines, etc.)
            has_complex_surfaces = any(
                f.get("type") in ["spherical", "conical", "toroidal"]
                for f in face_features
            )
            if has_complex_surfaces:
                geometry_found.append("complex surfaces (fillets, rounds, or sculpted geometry)")

            geometry_description = ", ".join(geometry_found) if geometry_found else "various geometry"

            return _format_response({
                "status": "no_features",
                "message": (
                    f"No automatically recognizable features detected in '{body.name}'. "
                    f"Found {geometry_description}, but no simple holes, pockets, or slots that Fusion's feature recognition can identify."
                ),
                "body_name": body.name,
                "material": material,
                "limitations": {
                    "detected_types": [
                        "Simple holes (drilled, counterbored, countersunk)",
                        "Rectangular pockets",
                        "Slots"
                    ],
                    "not_detected": [
                        "Threaded holes (use Thread operation manually)",
                        "Complex surface geometry (NURBS, splines, sculpted surfaces)",
                        "Chamfers, fillets, and radii (considered finish features)",
                        "Holes in patterns that weren't modeled with Hole feature",
                        "Non-standard pocket shapes or blind cavities"
                    ]
                },
                "geometry_found": {
                    "cylindrical_faces": cylindrical_count,
                    "planar_faces": planar_count,
                    "has_complex_surfaces": has_complex_surfaces
                },
                "next_steps": (
                    "For this part, you'll need to create CAM operations manually in Fusion 360. "
                    "Typical strategy: (1) Adaptive Clearing for roughing, (2) Contour for walls/profiles, "
                    "(3) Scallop or Parallel for complex surfaces, (4) Thread Milling for threaded holes."
                )
            })

        # ---------------------------------------------------------------------
        # Get tool library
        # ---------------------------------------------------------------------
        tools_result = handle_get_tool_library({})
        tools_data = None
        try:
            content = tools_result.get('content', [])
            if content and len(content) > 0:
                tools_data = json.loads(content[0].get('text', '{}'))
        except Exception:
            pass

        if not tools_data or tools_data.get('error'):
            return _format_error(
                "Failed to get tool library",
                str(tools_data.get('error') if tools_data else 'Unknown error')
            )

        available_tools = tools_data.get('tools', [])

        if not available_tools:
            return _format_error(
                "No tools available in document library",
                "Add tools to the document library before requesting toolpath suggestions"
            )

        # ---------------------------------------------------------------------
        # Preference check
        # ---------------------------------------------------------------------
        mcp_call_func = arguments.get('_mcp_call_func')
        preferences_by_feature_type = {}

        if mcp_call_func and not use_defaults:
            # Initialize schema (safe to call multiple times)
            initialize_strategy_schema(mcp_call_func)

            # Try to get stored preferences for each unique feature type
            feature_types_seen = set()
            for feature in features_by_priority:
                ftype = feature.get('type', 'unknown')
                if ftype not in feature_types_seen:
                    feature_types_seen.add(ftype)
                    pref = get_strategy_preference(material, ftype, mcp_call_func)
                    if pref:
                        preferences_by_feature_type[ftype] = pref

        # ---------------------------------------------------------------------
        # Learning integration: adjust confidence from feedback history
        # ---------------------------------------------------------------------
        learning_metadata = None
        if FEEDBACK_LEARNING_AVAILABLE and mcp_call_func:
            try:
                initialize_feedback_schema(mcp_call_func)
                feedback_history = get_matching_feedback(
                    operation_type="toolpath_strategy",
                    material=material,
                    geometry_type=geometry_type,
                    limit=50,
                    mcp_call_func=mcp_call_func
                )
                if feedback_history:
                    base_confidence = 0.8  # Default toolpath strategy confidence
                    adjusted_confidence, learning_source = adjust_confidence_from_feedback(
                        base_confidence=base_confidence,
                        feedback_history=feedback_history
                    )
                    learning_metadata = {
                        "sample_count": len(feedback_history),
                        "adjusted_confidence": adjusted_confidence,
                        "source": learning_source
                    }
                    # First-time learning notification
                    if should_notify_learning(feedback_history):
                        learning_metadata["notification"] = (
                            f"I noticed patterns in your preferences for {material}. "
                            "Future suggestions will reflect what you've chosen before."
                        )
            except Exception:
                pass  # Learning is non-critical, don't break suggestions

        # ---------------------------------------------------------------------
        # Process each feature to generate suggestions
        # ---------------------------------------------------------------------
        suggestions = []

        for feature in features_by_priority:
            feature_type = feature.get('type', 'unknown')

            # Check if we have a preference override
            preference = preferences_by_feature_type.get(feature_type)

            # Map feature to operations (uses default rules)
            operation_mapping = map_feature_to_operations(feature, material)

            # Apply preference override if available
            if preference and not use_defaults:
                roughing_op = preference.get('preferred_roughing_op') or operation_mapping['roughing']['operation_type']
                finishing_op = preference.get('preferred_finishing_op') or operation_mapping['finishing']['operation_type']
                source = "from: user_preference"
            else:
                roughing_op = operation_mapping['roughing']['operation_type']
                finishing_op = operation_mapping['finishing']['operation_type']
                source = "from: default_rules"

            # Select tool for this feature
            # For drilling operations, filter to drills; otherwise use all endmills
            tool_filter = "drill" if roughing_op == "drilling" else None
            tool_selection = select_best_tool(feature, available_tools, tool_filter)

            # Handle case where no tool fits
            if tool_selection.get('status') != 'ok':
                suggestion = {
                    "feature": {
                        "type": feature_type,
                        "id": feature.get("id"),
                        "dimensions": {}
                    },
                    "status": "no_tool_available",
                    "reason": tool_selection.get('reason', 'No fitting tool found'),
                    "constraint": tool_selection.get('constraint', {})
                }

                # Add relevant dimensions based on feature type
                if feature_type == "hole":
                    suggestion["feature"]["dimensions"]["diameter"] = feature.get("diameter")
                    suggestion["feature"]["dimensions"]["depth"] = feature.get("depth")
                elif feature_type in ["pocket", "slot"]:
                    suggestion["feature"]["dimensions"]["depth"] = feature.get("depth")
                    suggestion["feature"]["dimensions"]["width"] = feature.get("width")
                    if feature.get("length"):
                        suggestion["feature"]["dimensions"]["length"] = feature.get("length")

                suggestions.append(suggestion)
                continue

            # Get selected tool
            selected_tool = tool_selection['tool']

            # Calculate feeds and speeds
            cutting_params = calculate_feeds_speeds(
                material=material,
                tool=selected_tool,
                is_carbide=is_carbide,
                operation_type="roughing"
            )

            # Build suggestion for this feature
            suggestion = {
                "feature": {
                    "type": feature_type,
                    "id": feature.get("id"),
                    "dimensions": {}
                },
                "roughing": {
                    "operation_type": roughing_op,
                    "confidence": operation_mapping['roughing']['confidence'],
                    "reasoning": operation_mapping['roughing']['reasoning']
                },
                "finishing": {
                    "operation_type": finishing_op,
                    "confidence": operation_mapping['finishing']['confidence'],
                    "reasoning": operation_mapping['finishing']['reasoning']
                },
                "recommended_tool": {
                    "description": selected_tool.get("description", "Tool"),
                    "diameter": selected_tool.get("diameter"),
                    "type": selected_tool.get("type"),
                    "flutes": selected_tool.get("flutes"),
                    "reasoning": tool_selection.get("reasoning", "Best fitting tool")
                },
                "cutting_parameters": {
                    "rpm": cutting_params.get("rpm"),
                    "feed_rate": cutting_params.get("feed_rate"),
                    "stepover_roughing": cutting_params.get("stepover_roughing"),
                    "stepover_finishing": cutting_params.get("stepover_finishing"),
                    "stepdown_roughing": cutting_params.get("stepdown_roughing")
                }
            }

            # Add relevant dimensions based on feature type
            if feature_type == "hole":
                suggestion["feature"]["dimensions"]["diameter"] = feature.get("diameter")
                suggestion["feature"]["dimensions"]["depth"] = feature.get("depth")
            elif feature_type in ["pocket", "slot"]:
                suggestion["feature"]["dimensions"]["depth"] = feature.get("depth")
                suggestion["feature"]["dimensions"]["width"] = feature.get("width")
                if feature.get("length"):
                    suggestion["feature"]["dimensions"]["length"] = feature.get("length")
                if feature.get("min_corner_radius"):
                    suggestion["feature"]["dimensions"]["min_corner_radius"] = feature.get("min_corner_radius")

            suggestions.append(suggestion)

        # ---------------------------------------------------------------------
        # Save preferences if requested
        # ---------------------------------------------------------------------
        if save_as_pref and mcp_call_func:
            feature_types_saved = set()
            for suggestion in suggestions:
                if suggestion.get("status") == "no_tool_available":
                    continue  # Skip suggestions without tools

                ftype = suggestion["feature"]["type"]
                if ftype in feature_types_saved:
                    continue  # Already saved this feature type

                feature_types_saved.add(ftype)

                pref_dict = {
                    "preferred_roughing_op": suggestion["roughing"]["operation_type"],
                    "preferred_finishing_op": suggestion["finishing"]["operation_type"],
                    "preferred_tool_diameter_mm": suggestion["recommended_tool"]["diameter"]["value"],
                    "confidence_score": suggestion["roughing"]["confidence"]
                }

                save_strategy_preference(material, ftype, pref_dict, mcp_call_func)

        # ---------------------------------------------------------------------
        # Build final response
        # ---------------------------------------------------------------------
        response = {
            "status": "success",
            "material": material,
            "is_carbide": is_carbide,
            "feature_count": len(features_by_priority),
            "suggestions": suggestions,
            "processing_order": "drilling -> roughing -> finishing",
            "source": source,
            "note": "These are starting-point suggestions. Adjust based on machine rigidity, workholding, and tool condition.",
            "learning_metadata": learning_metadata
        }

        return _format_response(response)

    except Exception as e:
        import traceback
        return _format_error(f"Failed to suggest toolpath strategy: {str(e)}", traceback.format_exc())


# =============================================================================
# FEEDBACK LEARNING HANDLERS
# =============================================================================

def handle_record_user_choice(arguments: dict) -> dict:
    """
    Record user acceptance or override of a suggestion for learning.

    Stores feedback events in SQLite via MCP bridge. The system learns from
    these events and adjusts future suggestion confidence scores based on
    acceptance rates.

    Arguments:
        operation_type (str, required): 'stock_setup', 'toolpath_strategy', 'tool_selection'
        material (str, required): Material name
        geometry_type (str, optional): Geometry classification
        body_name (str, optional): Part body name for auto-detection of geometry_type
        suggestion (dict, required): Original suggestion that was presented
        user_choice (dict, optional): What user selected instead. NULL/omit = accepted suggestion.
        feedback_type (str, optional): Default 'implicit'. Can be 'explicit_good' or 'explicit_bad'.
        note (str, optional): Reason for override

    Returns:
        Success response with recorded feedback details or error
    """
    try:
        # Check module availability
        if not FEEDBACK_LEARNING_AVAILABLE:
            return _format_error(
                "Feedback learning module not available",
                "Import failed for feedback_learning module"
            )

        # Validate required fields
        operation_type = arguments.get('operation_type')
        material = arguments.get('material')
        suggestion = arguments.get('suggestion')

        if not operation_type:
            return _format_error("Missing required field: operation_type")
        if not material:
            return _format_error("Missing required field: material")
        if not suggestion:
            return _format_error("Missing required field: suggestion")

        # Get or auto-detect geometry_type
        geometry_type = arguments.get('geometry_type')
        body_name = arguments.get('body_name')

        if not geometry_type and body_name:
            # Auto-detect geometry_type from body_name
            if not FUSION_AVAILABLE:
                return _format_error("Fusion 360 API not available for geometry auto-detection")

            try:
                # Run geometry analysis
                analysis_result = handle_analyze_geometry_for_cam({
                    'body_names': [body_name],
                    'analysis_type': 'full'
                })

                # Extract features
                analysis_data = None
                content = analysis_result.get('content', [])
                if content and len(content) > 0:
                    analysis_data = json.loads(content[0].get('text', '{}'))

                if analysis_data and not analysis_data.get('error'):
                    body_result = analysis_data.get('results', [{}])[0]
                    recognized_features = body_result.get('recognized_features', {})
                    all_features = []
                    if recognized_features:
                        all_features.extend(recognized_features.get('holes', []))
                        all_features.extend(recognized_features.get('pockets', []))
                        all_features.extend(recognized_features.get('slots', []))

                    # Classify geometry type
                    if STOCK_SUGGESTIONS_AVAILABLE:
                        geometry_type = classify_geometry_type(all_features)
            except Exception:
                pass  # Failed to auto-detect, will check below

        if not geometry_type:
            return _format_error(
                "Missing geometry_type",
                "Provide either geometry_type or body_name for auto-detection"
            )

        # Get other optional fields
        user_choice = arguments.get('user_choice')
        feedback_type = arguments.get('feedback_type', 'implicit')
        note = arguments.get('note')

        # Auto-detect feedback_type if 'implicit'
        if feedback_type == 'implicit':
            if user_choice is None:
                feedback_type = 'implicit_accept'
            else:
                feedback_type = 'implicit_reject'

        # Build context snapshot
        context = {
            "operation_type": operation_type,
            "material": material,
            "geometry_type": geometry_type
        }

        # Get MCP call function
        mcp_call_func = arguments.get('_mcp_call_func')
        if not mcp_call_func:
            return _format_error("MCP call function not available")

        # Initialize schema (safe to call multiple times)
        initialize_feedback_schema(mcp_call_func)

        # Record feedback
        record_feedback(
            operation_type=operation_type,
            material=material,
            geometry_type=geometry_type,
            context=context,
            suggestion=suggestion,
            user_choice=user_choice,
            feedback_type=feedback_type,
            note=note,
            mcp_call_func=mcp_call_func
        )

        # Build response
        response = {
            "status": "recorded",
            "operation_type": operation_type,
            "feedback_type": feedback_type,
            "message": "Feedback recorded successfully",
            "context": context
        }

        return _format_response(response)

    except Exception as e:
        import traceback
        return _format_error(f"Failed to record user choice: {str(e)}", traceback.format_exc())


def handle_get_feedback_stats(arguments: dict) -> dict:
    """
    Get feedback statistics for learning system.

    Returns acceptance rates broken down by operation type, material,
    and geometry type.

    Arguments:
        operation_type (str, optional): Filter stats to specific operation type

    Returns:
        Statistics dict with overall and per-category breakdowns
    """
    try:
        # Check module availability
        if not FEEDBACK_LEARNING_AVAILABLE:
            return _format_error(
                "Feedback learning module not available",
                "Import failed for feedback_learning module"
            )

        # Get MCP call function
        mcp_call_func = arguments.get('_mcp_call_func')
        if not mcp_call_func:
            return _format_error("MCP call function not available")

        # Initialize schema
        initialize_feedback_schema(mcp_call_func)

        # Get optional filter
        operation_type = arguments.get('operation_type')

        # Get statistics
        stats = get_feedback_statistics(operation_type, mcp_call_func)

        return _format_response(stats)

    except Exception as e:
        import traceback
        return _format_error(f"Failed to get feedback stats: {str(e)}", traceback.format_exc())


def handle_export_feedback_history(arguments: dict) -> dict:
    """
    Export feedback history as CSV or JSON.

    Arguments:
        format (str, optional): 'csv' or 'json' (default: 'json')
        operation_type (str, optional): Filter export to specific operation type

    Returns:
        Export string in requested format
    """
    try:
        # Check module availability
        if not FEEDBACK_LEARNING_AVAILABLE:
            return _format_error(
                "Feedback learning module not available",
                "Import failed for feedback_learning module"
            )

        # Get MCP call function
        mcp_call_func = arguments.get('_mcp_call_func')
        if not mcp_call_func:
            return _format_error("MCP call function not available")

        # Initialize schema
        initialize_feedback_schema(mcp_call_func)

        # Get arguments
        format_type = arguments.get('format', 'json')
        operation_type = arguments.get('operation_type')

        # Export history
        export_data = export_feedback_history(format_type, operation_type, mcp_call_func)

        response = {
            "status": "success",
            "format": format_type,
            "data": export_data
        }

        return _format_response(response)

    except Exception as e:
        import traceback
        return _format_error(f"Failed to export feedback history: {str(e)}", traceback.format_exc())


def handle_clear_feedback_history(arguments: dict) -> dict:
    """
    Clear feedback history (all or specific operation type).

    Requires explicit confirmation to prevent accidental data loss.

    Arguments:
        operation_type (str, optional): If provided, clear only that category. If omitted, clear all.
        confirm (bool, required): Must be true to proceed (safety check)

    Returns:
        Success response with deleted count
    """
    try:
        # Check module availability
        if not FEEDBACK_LEARNING_AVAILABLE:
            return _format_error(
                "Feedback learning module not available",
                "Import failed for feedback_learning module"
            )

        # Check confirmation
        confirm = arguments.get('confirm')
        if confirm != True:
            return _format_error(
                "Confirmation required",
                "Set confirm=true to clear feedback history"
            )

        # Get MCP call function
        mcp_call_func = arguments.get('_mcp_call_func')
        if not mcp_call_func:
            return _format_error("MCP call function not available")

        # Initialize schema
        initialize_feedback_schema(mcp_call_func)

        # Get optional filter
        operation_type = arguments.get('operation_type')

        # Clear history
        deleted_count = clear_feedback_history(operation_type, mcp_call_func)

        response = {
            "status": "success",
            "deleted_count": deleted_count,
            "operation_type": operation_type if operation_type else "all"
        }

        return _format_response(response)

    except Exception as e:
        import traceback
        return _format_error(f"Failed to clear feedback history: {str(e)}", traceback.format_exc())


# =============================================================================
# OPERATION ROUTER
# =============================================================================

def route_cam_operation(operation: str, arguments: dict) -> dict:
    """
    Route CAM operation to appropriate handler.

    Called from mcp_integration.py for CAM-specific operations.
    """
    handlers = {
        'get_cam_state': handle_get_cam_state,
        'get_tool_library': handle_get_tool_library,
        'analyze_geometry_for_cam': handle_analyze_geometry_for_cam,
        'suggest_stock_setup': handle_suggest_stock_setup,
        'suggest_toolpath_strategy': handle_suggest_toolpath_strategy,
        'record_user_choice': handle_record_user_choice,
        'get_feedback_stats': handle_get_feedback_stats,
        'export_feedback_history': handle_export_feedback_history,
        'clear_feedback_history': handle_clear_feedback_history,
        # Phase 6+
        # 'suggest_post_processor': handle_suggest_post_processor,
    }

    handler = handlers.get(operation)
    if handler:
        return handler(arguments)
    else:
        return _format_error(f"Unknown CAM operation: {operation}",
                           f"Available operations: {list(handlers.keys())}")
