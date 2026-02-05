# Fusion 360 CAM AI Assistant

An AI-powered CAM workflow assistant for Autodesk Fusion 360. Analyzes geometry, suggests stock setup, toolpath strategies, and learns from your preferences.

**Built as an extension to [Fusion-360-MCP-Server](https://github.com/AuraFriday/Fusion-360-MCP-Server) by [@AuraFriday](https://github.com/AuraFriday).**

## What It Does

- **Analyze Geometry** — Extracts CAM-relevant features (pockets, holes, contours), calculates bounding boxes, identifies minimum tool radii
- **Suggest Stock Setup** — Recommends stock dimensions and orientation based on part geometry and your preferences
- **Recommend Toolpath Strategy** — Suggests roughing/finishing approaches, tool selection, feeds and speeds
- **Learn from Choices** — Stores your preferences and improves suggestions over time

## How It Works

```
Your AI Assistant (Claude, etc.)
         │
         ▼ MCP Protocol
┌─────────────────────────────────┐
│     MCP-Link Server             │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  Fusion 360 + MCP Add-in        │
│  ├── Original MCP Server        │ ← AuraFriday's foundation
│  └── CAM Extension              │ ← This project
└─────────────────────────────────┘
         │
         ▼
    Fusion 360 CAM API
```

## Installation

### Prerequisites

1. **Autodesk Fusion 360** installed
2. **MCP-Link Server** from [AuraFriday's releases](https://github.com/AuraFriday/Fusion-360-MCP-Server/releases)

### Install the Add-in

1. Clone this repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/fusion360-cam-assistant.git
   ```

2. In Fusion 360, press `Shift+S` to open Scripts and Add-Ins

3. Click the green `+` next to "My Add-Ins"

4. Navigate to the `Fusion-360-MCP-Server` folder in this repo

5. Click "Run" to start the add-in

6. Check the TEXT COMMANDS window (`View → Show Panel → Text Commands`) for connection status

## CAM Operations

### get_cam_state

Query current CAM workspace state.

```json
{
  "operation": "get_cam_state"
}
```

Returns: setups, operations, stock configuration, post-processor info.

### get_tool_library

Query available cutting tools.

```json
{
  "operation": "get_tool_library",
  "filter": {
    "type": ["endmill", "drill"],
    "diameter_range": [3.0, 20.0]
  },
  "limit": 50
}
```

Returns: tools with diameter, flutes, lengths, vendor info.

### analyze_geometry_for_cam

Analyze part geometry for manufacturability.

```json
{
  "operation": "analyze_geometry_for_cam",
  "body_names": ["Part1"],
  "analysis_type": "full"
}
```

Returns:
- Bounding box with dimensions
- Volume and surface area
- Detected features (cylindrical, planar, conical)
- Minimum internal radius (for tool selection)
- Orientation suggestions with scores

### suggest_stock_setup (coming soon)

Recommend stock dimensions and orientation.

### suggest_toolpath_strategy (coming soon)

Recommend machining strategies, tools, and parameters.

### record_user_choice (coming soon)

Store feedback for preference learning.

## Project Structure

```
fusion360-cam-assistant/
├── README.md
├── LICENSE
├── Fusion-360-MCP-Server/      # Extended MCP server
│   ├── MCP-Link.py             # Entry point
│   ├── mcp_integration.py      # Core + CAM routing
│   ├── cam_operations.py       # CAM-specific handlers
│   ├── lib/                    # MCP client library
│   └── tool_libraries/         # Reference tool libraries
│       └── carvera/            # Carvera community tools
├── .planning/                  # Development roadmap
│   ├── PROJECT.md
│   ├── ROADMAP.md
│   └── phases/
└── docs/                       # Additional documentation
```

## Tool Libraries

Includes reference tool libraries from the [Carvera Community](https://github.com/Carvera-Community/Carvera_Community_Profiles):
- Ball endmills
- Drill bits
- O-flute bits (for plastics/aluminum)

## Roadmap

See [.planning/ROADMAP.md](.planning/ROADMAP.md) for detailed implementation phases.

**Milestone 1: CAM Extension MVP**
- [x] Phase 1: CAM state access, tool library queries
- [x] Phase 2: Geometry analysis
- [ ] Phase 3: Stock suggestions
- [ ] Phase 4: Toolpath strategy suggestions
- [ ] Phase 5: Learning system
- [ ] Phase 6: Post-processor matching

**Future Milestones**
- Real-time UI observation
- Advanced ML-based learning
- Simulation integration

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Areas where help is needed:
- Testing with different machine types
- CAM strategy rules for various materials
- Tool library contributions
- Documentation improvements

## Credits

This project builds upon:

- **[Fusion-360-MCP-Server](https://github.com/AuraFriday/Fusion-360-MCP-Server)** by [@AuraFriday](https://github.com/AuraFriday) — The foundation MCP server that makes AI-Fusion 360 integration possible. Licensed under their terms.

- **[Carvera Community Profiles](https://github.com/Carvera-Community/Carvera_Community_Profiles)** — Tool library definitions used as reference.

- **[Model Context Protocol (MCP)](https://modelcontextprotocol.io/)** — The protocol enabling AI tool integration.

## License

This CAM extension is licensed under the MIT License. See [LICENSE](LICENSE) for details.

**Note:** The underlying Fusion-360-MCP-Server has its own license terms. Please review [their repository](https://github.com/AuraFriday/Fusion-360-MCP-Server) for details.

## Disclaimer

This software is provided as-is. CAM operations can cause damage to machines, tools, and workpieces. Always verify generated suggestions before use. The authors are not responsible for any damages resulting from use of this software.
