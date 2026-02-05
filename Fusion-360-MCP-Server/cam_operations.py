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
                "is_active": setup == cam.activeSetup,
                "operations": [],
                "stock": None,
                "wcs_origin": None
            }

            # Get stock configuration
            try:
                stock_mode = setup.stockMode

                if stock_mode == adsk.cam.StockModes.FixedBoxStock:
                    setup_info["stock"] = {
                        "type": "fixed_box",
                        "mode": "FixedBoxStock"
                    }
                    # Get dimensions with explicit units
                    try:
                        params = setup.parameters
                        x_param = params.itemByName("job_stockFixedX")
                        y_param = params.itemByName("job_stockFixedY")
                        z_param = params.itemByName("job_stockFixedZ")

                        setup_info["stock"]["dimensions"] = {
                            "x": {
                                "expression": x_param.expression if x_param else None,
                                "value": _to_mm(x_param.value.value) if x_param and x_param.value else None
                            },
                            "y": {
                                "expression": y_param.expression if y_param else None,
                                "value": _to_mm(y_param.value.value) if y_param and y_param.value else None
                            },
                            "z": {
                                "expression": z_param.expression if z_param else None,
                                "value": _to_mm(z_param.value.value) if z_param and z_param.value else None
                            }
                        }
                    except:
                        pass

                elif stock_mode == adsk.cam.StockModes.RelativeBoxStock:
                    setup_info["stock"] = {
                        "type": "relative_box",
                        "mode": "RelativeBoxStock"
                    }
                    # Get offsets with explicit units
                    try:
                        params = setup.parameters
                        side_param = params.itemByName("job_stockOffsetSides")
                        top_param = params.itemByName("job_stockOffsetTop")
                        bottom_param = params.itemByName("job_stockOffsetBottom")

                        setup_info["stock"]["offsets"] = {
                            "side": {
                                "expression": side_param.expression if side_param else None,
                                "value": _to_mm(side_param.value.value) if side_param and side_param.value else None
                            },
                            "top": {
                                "expression": top_param.expression if top_param else None,
                                "value": _to_mm(top_param.value.value) if top_param and top_param.value else None
                            },
                            "bottom": {
                                "expression": bottom_param.expression if bottom_param else None,
                                "value": _to_mm(bottom_param.value.value) if bottom_param and bottom_param.value else None
                            }
                        }
                    except:
                        pass

                elif stock_mode == adsk.cam.StockModes.FromSolidStock:
                    setup_info["stock"] = {
                        "type": "from_solid",
                        "mode": "FromSolidStock"
                    }

                elif stock_mode == adsk.cam.StockModes.CylinderStock:
                    setup_info["stock"] = {
                        "type": "cylinder",
                        "mode": "CylinderStock"
                    }
                    # Try to get cylinder dimensions
                    try:
                        params = setup.parameters
                        diameter_param = params.itemByName("job_stockCylinderDiameter")
                        height_param = params.itemByName("job_stockCylinderHeight")

                        if diameter_param or height_param:
                            setup_info["stock"]["dimensions"] = {}
                            if diameter_param:
                                setup_info["stock"]["dimensions"]["diameter"] = {
                                    "expression": diameter_param.expression,
                                    "value": _to_mm(diameter_param.value.value) if diameter_param.value else None
                                }
                            if height_param:
                                setup_info["stock"]["dimensions"]["height"] = {
                                    "expression": height_param.expression,
                                    "value": _to_mm(height_param.value.value) if height_param.value else None
                                }
                    except:
                        pass

            except Exception as e:
                setup_info["stock"] = {"error": str(e)}

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

        # Get post-processor info if set
        post_info = None
        try:
            if cam.activeSetup:
                post = cam.activeSetup.postProcess
                if post:
                    post_info = {
                        "name": post.name if hasattr(post, 'name') else None
                    }
        except:
            pass

        result = {
            "has_cam_workspace": True,
            "setup_count": len(setups_data),
            "setups": setups_data,
            "active_setup": cam.activeSetup.name if cam.activeSetup else None,
            "post_processor": post_info
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

                        # Get tool properties
                        tool_type_str = ""
                        try:
                            tool_type = tool.type
                            if hasattr(tool_type, 'toString'):
                                tool_type_str = tool_type.toString()
                            else:
                                tool_type_str = str(tool_type)
                        except:
                            tool_type_str = "unknown"

                        # Diameter in mm for filtering
                        diameter_cm = tool.diameter if hasattr(tool, 'diameter') else 0
                        diameter_mm = diameter_cm * 10

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
                            "description": tool.description if hasattr(tool, 'description') else "",
                            "type": tool_type_str,
                            "diameter": _to_mm(diameter_cm),
                            "library": "Document Tools"
                        }

                        # Add additional properties
                        if hasattr(tool, 'numberOfFlutes'):
                            tool_info["flutes"] = tool.numberOfFlutes
                        if hasattr(tool, 'fluteLength'):
                            tool_info["flute_length"] = _to_mm(tool.fluteLength)
                        if hasattr(tool, 'overallLength'):
                            tool_info["overall_length"] = _to_mm(tool.overallLength)
                        if hasattr(tool, 'shaftDiameter'):
                            tool_info["shaft_diameter"] = _to_mm(tool.shaftDiameter)
                        if hasattr(tool, 'vendor'):
                            tool_info["vendor"] = tool.vendor

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

                    # Limit features in output to avoid huge responses
                    body_result["features"] = features[:20]
                    if len(features) > 20:
                        body_result["features_truncated"] = True
                        body_result["total_features"] = len(features)

                    body_result["min_internal_radius_mm"] = round(min_radius, 3) if min_radius != float('inf') else None

                # Orientation suggestions based on bounding box
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
        # Phase 3+
        # 'suggest_stock_setup': handle_suggest_stock_setup,
        # 'suggest_toolpath_strategy': handle_suggest_toolpath_strategy,
        # 'record_user_choice': handle_record_user_choice,
        # 'suggest_post_processor': handle_suggest_post_processor,
    }

    handler = handlers.get(operation)
    if handler:
        return handler(arguments)
    else:
        return _format_error(f"Unknown CAM operation: {operation}",
                           f"Available operations: {list(handlers.keys())}")
