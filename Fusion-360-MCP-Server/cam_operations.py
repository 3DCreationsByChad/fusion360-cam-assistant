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
                    # Try to get dimensions if available
                    try:
                        setup_info["stock"]["dimensions"] = {
                            "x": setup.parameters.itemByName("job_stockFixedX").expression,
                            "y": setup.parameters.itemByName("job_stockFixedY").expression,
                            "z": setup.parameters.itemByName("job_stockFixedZ").expression
                        }
                    except:
                        pass

                elif stock_mode == adsk.cam.StockModes.RelativeBoxStock:
                    setup_info["stock"] = {
                        "type": "relative_box",
                        "mode": "RelativeBoxStock"
                    }
                    # Try to get offsets
                    try:
                        setup_info["stock"]["offsets"] = {
                            "side": setup.parameters.itemByName("job_stockOffsetSides").expression,
                            "top": setup.parameters.itemByName("job_stockOffsetTop").expression,
                            "bottom": setup.parameters.itemByName("job_stockOffsetBottom").expression
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

            except Exception as e:
                setup_info["stock"] = {"error": str(e)}

            # Get WCS origin info
            try:
                origin = setup.parameters.itemByName("job_stockZPosition")
                if origin:
                    setup_info["wcs_origin"] = origin.expression
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

                # Try to get tool info
                try:
                    tool = op.tool
                    if tool:
                        op_info["tool"] = {
                            "description": tool.description,
                            "type": tool.type.toString() if hasattr(tool.type, 'toString') else str(tool.type),
                            "diameter": tool.diameter * 10  # cm to mm
                        }
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

        # Get tool libraries
        library_manager = cam.libraryManager
        tool_libraries = library_manager.toolLibraries

        # List available libraries
        available_libraries = []
        for lib_url in tool_libraries.libraryUrls:
            lib = tool_libraries.libraryAtUrl(lib_url)
            if lib:
                available_libraries.append({
                    "name": lib.name,
                    "url": lib_url.url if hasattr(lib_url, 'url') else str(lib_url),
                    "tool_count": lib.count if hasattr(lib, 'count') else None
                })

        # Collect tools
        tools_data = []

        for lib_url in tool_libraries.libraryUrls:
            lib = tool_libraries.libraryAtUrl(lib_url)
            if not lib:
                continue

            # Filter by library name if specified
            if library_name and lib.name != library_name:
                continue

            # Iterate through tools in library
            for i in range(lib.count):
                if len(tools_data) >= limit:
                    break

                try:
                    tool = lib.item(i)

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

                    # Diameter in mm (Fusion uses cm internally)
                    diameter_mm = tool.diameter * 10 if hasattr(tool, 'diameter') else 0

                    # Apply filters
                    if type_filter:
                        type_match = any(t.lower() in tool_type_str.lower() for t in type_filter)
                        if not type_match:
                            continue

                    if diameter_range:
                        if diameter_mm < diameter_range[0] or diameter_mm > diameter_range[1]:
                            continue

                    # Build tool info
                    tool_info = {
                        "description": tool.description if hasattr(tool, 'description') else "",
                        "type": tool_type_str,
                        "diameter_mm": round(diameter_mm, 3),
                        "library": lib.name
                    }

                    # Add additional properties if available
                    if hasattr(tool, 'numberOfFlutes'):
                        tool_info["flutes"] = tool.numberOfFlutes

                    if hasattr(tool, 'fluteLength'):
                        tool_info["flute_length_mm"] = round(tool.fluteLength * 10, 2)

                    if hasattr(tool, 'overallLength'):
                        tool_info["overall_length_mm"] = round(tool.overallLength * 10, 2)

                    if hasattr(tool, 'shaftDiameter'):
                        tool_info["shaft_diameter_mm"] = round(tool.shaftDiameter * 10, 3)

                    if hasattr(tool, 'bodyLength'):
                        tool_info["body_length_mm"] = round(tool.bodyLength * 10, 2)

                    if hasattr(tool, 'cornerRadius'):
                        tool_info["corner_radius_mm"] = round(tool.cornerRadius * 10, 3)

                    if hasattr(tool, 'taperAngle'):
                        tool_info["taper_angle"] = tool.taperAngle

                    if hasattr(tool, 'productId'):
                        tool_info["product_id"] = tool.productId

                    if hasattr(tool, 'vendor'):
                        tool_info["vendor"] = tool.vendor

                    # Tool material (carbide, HSS, etc.)
                    if hasattr(tool, 'material'):
                        try:
                            tool_info["tool_material"] = str(tool.material)
                        except:
                            pass

                    tools_data.append(tool_info)

                except Exception as tool_error:
                    # Skip tools that can't be read
                    continue

            if len(tools_data) >= limit:
                break

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
