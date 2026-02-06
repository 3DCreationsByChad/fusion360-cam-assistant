"""Feature-to-operation mapping for CAM toolpath strategy.

Maps detected features to recommended CAM operations with confidence
scoring and reasoning based on feature geometry and material properties.
"""

from .material_library import get_material_properties


# Operation mapping rules by feature type
OPERATION_RULES = {
    "hole": {
        "conditions": [
            {
                "test": lambda f, m: f.get("diameter", {}).get("value", 0) < 12,
                "roughing": "drilling",
                "finishing": "drilling",  # Drilling is self-finishing
                "confidence": 0.95,
                "reasoning": "Small hole (diameter < 12mm) best suited for drilling"
            },
            {
                "test": lambda f, m: f.get("diameter", {}).get("value", 0) >= 12,
                "roughing": "helical_milling",
                "finishing": "helical_milling",  # Or could use boring for finishing
                "confidence": 0.85,
                "reasoning": "Large hole (diameter >= 12mm) requires helical milling or boring"
            }
        ],
        "default": {
            "roughing": "drilling",
            "finishing": "drilling",
            "confidence": 0.70,
            "reasoning": "Default drilling operation for hole"
        }
    },
    "pocket": {
        "conditions": [
            {
                "test": lambda f, m: (
                    f.get("depth", {}).get("value", 0) > 10 and
                    m.get("hardness", "medium") != "soft"
                ),
                "roughing": "adaptive_clearing",
                "finishing": "2d_contour",
                "confidence": 0.90,
                "reasoning": "Deep pocket (>10mm) in medium/hard material requires adaptive clearing"
            },
            {
                "test": lambda f, m: (
                    f.get("depth", {}).get("value", 0) <= 10 or
                    m.get("hardness", "medium") == "soft"
                ),
                "roughing": "2d_pocket",
                "finishing": "2d_contour",
                "confidence": 0.85,
                "reasoning": "Shallow pocket or soft material suitable for 2D pocket operation"
            }
        ],
        "default": {
            "roughing": "2d_pocket",
            "finishing": "2d_contour",
            "confidence": 0.75,
            "reasoning": "Standard 2D pocket with contour finishing"
        }
    },
    "slot": {
        "conditions": [
            {
                "test": lambda f, m: (
                    f.get("width", {}).get("value", 0) > 0 and
                    # Note: tool diameter comparison would happen in tool selection,
                    # this is just feature analysis
                    f.get("width", {}).get("value", 0) <= 20  # Arbitrary threshold for "narrow"
                ),
                "roughing": "slot_milling",
                "finishing": "2d_contour",
                "confidence": 0.90,
                "reasoning": "Narrow slot suitable for dedicated slot milling"
            },
            {
                "test": lambda f, m: f.get("width", {}).get("value", 0) > 20,
                "roughing": "adaptive_clearing",
                "finishing": "2d_contour",
                "confidence": 0.85,
                "reasoning": "Wide slot requires adaptive clearing for efficient material removal"
            }
        ],
        "default": {
            "roughing": "slot_milling",
            "finishing": "2d_contour",
            "confidence": 0.80,
            "reasoning": "Standard slot milling operation"
        }
    }
}

# Default fallback for unknown feature types
DEFAULT_OPERATION = {
    "roughing": "2d_contour",
    "finishing": "2d_contour",
    "confidence": 0.50,
    "reasoning": "Unknown feature type, defaulting to 2D contour"
}


def map_feature_to_operations(feature: dict, material: str) -> dict:
    """Map a feature to recommended CAM operations.

    Evaluates feature geometry and material properties to recommend
    both roughing and finishing operations with confidence scores.

    Args:
        feature: Feature dict with keys:
            - type: str (e.g., "hole", "pocket", "slot")
            - diameter, depth, width, etc. (geometry properties)
            All dimensional values in format: {"value": X, "unit": "mm"}
        material: Material name (passed to get_material_properties)

    Returns:
        dict with structure:
        {
            "feature_type": str,
            "roughing": {
                "operation_type": str,
                "confidence": float (0.0-1.0),
                "reasoning": str,
                "priority": int (1=drilling, 2=roughing, 3=finishing)
            },
            "finishing": {
                "operation_type": str,
                "confidence": float,
                "reasoning": str,
                "priority": int
            },
            "source": "from: default_rules"
        }
    """
    # Get feature type
    feature_type = feature.get("type", "unknown").lower()

    # Get material properties for condition evaluation
    mat_props = get_material_properties(material)

    # Look up operation rules for this feature type
    rules = OPERATION_RULES.get(feature_type)

    if rules is None:
        # Unknown feature type - use default
        result = {
            "feature_type": feature_type,
            "roughing": {
                "operation_type": DEFAULT_OPERATION["roughing"],
                "confidence": DEFAULT_OPERATION["confidence"],
                "reasoning": DEFAULT_OPERATION["reasoning"],
                "priority": 2  # Default priority
            },
            "finishing": {
                "operation_type": DEFAULT_OPERATION["finishing"],
                "confidence": DEFAULT_OPERATION["confidence"] * 0.9,  # Slightly lower for finishing
                "reasoning": "Standard contour finishing",
                "priority": 3
            },
            "source": "from: default_rules"
        }
        return result

    # Evaluate conditions to find matching rule
    selected_rule = None
    for condition in rules.get("conditions", []):
        try:
            if condition["test"](feature, mat_props):
                selected_rule = condition
                break
        except (KeyError, TypeError):
            # Condition evaluation failed (missing data), skip to next
            continue

    # Use default if no condition matched
    if selected_rule is None:
        selected_rule = rules["default"]

    # Determine priority based on operation type
    # Priority: 1=drilling, 2=roughing operations, 3=finishing
    roughing_op = selected_rule["roughing"]
    if roughing_op == "drilling":
        roughing_priority = 1
    else:
        roughing_priority = 2

    finishing_op = selected_rule["finishing"]
    if finishing_op == "drilling":
        finishing_priority = 1
    else:
        finishing_priority = 3

    # Build result
    result = {
        "feature_type": feature_type,
        "roughing": {
            "operation_type": roughing_op,
            "confidence": selected_rule["confidence"],
            "reasoning": selected_rule["reasoning"],
            "priority": roughing_priority
        },
        "finishing": {
            "operation_type": finishing_op,
            "confidence": selected_rule["confidence"] * 0.95,  # Finishing slightly lower confidence
            "reasoning": f"Standard {finishing_op} finishing for {feature_type}",
            "priority": finishing_priority
        },
        "source": "from: default_rules"
    }

    # For operations that are self-finishing (like drilling), unify the reasoning
    if roughing_op == finishing_op and roughing_op == "drilling":
        result["finishing"]["reasoning"] = "Drilling operation is self-finishing"

    return result
