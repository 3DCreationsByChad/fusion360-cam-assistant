# Upstream Project Attribution

This directory contains the **Fusion-360-MCP-Server** by [@AuraFriday](https://github.com/AuraFriday).

## Original Project

- **Repository:** https://github.com/AuraFriday/Fusion-360-MCP-Server
- **Author:** Christopher Nathan Drake (cnd)
- **License:** Proprietary (see [EULA.md](EULA.md) and [LICENSE](LICENSE))

## Modifications Made

The following files have been **added** by this CAM extension project:

- `cam_operations.py` — CAM-specific MCP operation handlers
- `CAM_EXTENSION_DESIGN.md` — Design documentation for CAM features
- `tool_libraries/carvera/` — Reference tool library CSVs
- `UPSTREAM.md` — This attribution file

The following files have been **modified**:

- `mcp_integration.py` — Added import and routing for CAM operations, updated tool description

## Keeping Up-to-Date

To incorporate upstream changes:

1. Check the original repo for updates
2. Download new releases from https://github.com/AuraFriday/Fusion-360-MCP-Server/releases
3. Merge changes carefully, preserving CAM extensions

## Thank You

This project would not be possible without the excellent foundation provided by AuraFriday's MCP server. Their work on:

- Thread-safe Fusion API access
- MCP protocol integration
- Generic API execution
- Python inline execution

...made building this CAM extension straightforward.

If you find this useful, please also star the original project:
https://github.com/AuraFriday/Fusion-360-MCP-Server
