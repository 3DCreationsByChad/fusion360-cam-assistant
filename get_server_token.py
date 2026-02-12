#!/usr/bin/env python3
"""
Try to get the actual auth token from MCP-Link server
"""

import json
from pathlib import Path

# Try to find server config files
config_locations = [
    Path.home() / "AppData" / "Roaming" / "AuraFriday" / "mcp-link-server" / "config.json",
    Path.home() / "AppData" / "Local" / "AuraFriday" / "config.json",
    Path.home() / "AppData" / "Roaming" / "AuraFriday" / "config.json",
]

print("Searching for MCP-Link server config files...\n")

for config_path in config_locations:
    if config_path.exists():
        print(f"✅ Found: {config_path}")
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)

            # Look for auth tokens
            if 'auth' in config:
                print(f"   Auth section found: {list(config['auth'].keys())}")

            if 'token' in config:
                print(f"   Token: {config['token']}")

            if 'apiKey' in config:
                print(f"   API Key: {config['apiKey']}")

            # Print full config (sanitized)
            print(f"\n   Full config keys: {list(config.keys())}")

        except Exception as e:
            print(f"   Error reading: {e}")

        print()
    else:
        print(f"❌ Not found: {config_path}")

print("\nIf no token found, try:")
print("1. Check MCP-Link server dashboard/settings")
print("2. Check server logs")
print("3. Or just use the hardcoded token (already configured)")
