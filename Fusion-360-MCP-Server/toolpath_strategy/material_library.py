"""Material property database for CNC machining calculations.

Provides surface feet per minute (SFM) values and chip load ranges
for common materials with both HSS and carbide tooling.
"""

# Material property database with SFM values and chip loads
MATERIAL_LIBRARY = {
    "aluminum": {
        "sfm_hss": 400,
        "sfm_carbide": 1200,
        "chip_load_range": (0.001, 0.003),  # inches/tooth
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
        "chip_load_range": (0.0003, 0.0015),
        "hardness": "hard"
    },
    "brass": {
        "sfm_hss": 300,
        "sfm_carbide": 900,
        "chip_load_range": (0.001, 0.003),
        "hardness": "soft"
    },
    "plastic": {
        "sfm_hss": 500,
        "sfm_carbide": 1500,
        "chip_load_range": (0.002, 0.004),
        "hardness": "soft"
    },
    "wood": {
        "sfm_hss": 600,
        "sfm_carbide": 1800,
        "chip_load_range": (0.003, 0.006),
        "hardness": "soft"
    }
}

# Conservative default for unknown materials
DEFAULT_MATERIAL = {
    "sfm_hss": 100,
    "sfm_carbide": 300,
    "chip_load_range": (0.0005, 0.001),
    "hardness": "medium"
}


def get_material_properties(material_name: str) -> dict:
    """Get material properties with intelligent lookup.

    Performs case-insensitive matching with partial name support.
    For example: "6061 aluminum" matches "aluminum",
                 "304 stainless" matches "stainless_steel"

    Args:
        material_name: Material name (e.g., "Aluminum", "6061 aluminum", "304 Stainless Steel")

    Returns:
        dict with keys: sfm_hss, sfm_carbide, chip_load_range, hardness, source
        Always includes "source" key indicating lookup result
    """
    # Normalize the input: lowercase, replace spaces and hyphens with underscores
    normalized = material_name.lower().replace(" ", "_").replace("-", "_")

    # Try exact match first
    if normalized in MATERIAL_LIBRARY:
        result = MATERIAL_LIBRARY[normalized].copy()
        result["source"] = "from: material_library"
        return result

    # Try partial match (check if any library key appears in the input)
    for lib_key, properties in MATERIAL_LIBRARY.items():
        if lib_key in normalized or normalized in lib_key:
            result = properties.copy()
            result["source"] = "from: material_library"
            return result

    # Also try matching library keys against the original normalized string
    # This handles cases like "stainless" matching "stainless_steel"
    for lib_key, properties in MATERIAL_LIBRARY.items():
        # Split both into words and check for overlap
        lib_words = set(lib_key.split("_"))
        input_words = set(normalized.split("_"))
        if lib_words & input_words:  # If there's any word overlap
            result = properties.copy()
            result["source"] = "from: material_library"
            return result

    # Fallback to conservative defaults
    result = DEFAULT_MATERIAL.copy()
    result["source"] = "from: default_conservative"
    return result
