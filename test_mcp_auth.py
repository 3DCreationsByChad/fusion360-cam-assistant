#!/usr/bin/env python3
"""
Standalone MCP Auth Tester
Run this script to check MCP-Link auth status WITHOUT starting Fusion 360
"""

import sys
import io
from pathlib import Path

# Fix Windows console encoding for Unicode output
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add lib directory to path
lib_path = Path(__file__).parent / "Fusion-360-MCP-Server" / "lib"
sys.path.insert(0, str(lib_path))

try:
    import auth_diagnostics

    print("\n" + "=" * 70)
    print("MCP AUTH STANDALONE TEST")
    print("=" * 70)
    print()

    # Run diagnostics
    report = auth_diagnostics.diagnose_auth()
    formatted = auth_diagnostics.format_report(report)

    print(formatted)

    # Detailed analysis
    print()
    print("DETAILED ANALYSIS:")
    print("-" * 70)

    if report["status"] == "ok":
        print("✅ Everything looks good!")
        print("   - MCP-Link is installed")
        print("   - Native binary is accessible")
        print("   - Auth tokens match")
        print()
        print("Next steps:")
        print("   1. Start Fusion 360")
        print("   2. Run the MCP-Link add-in")
        print("   3. Connection should work!")

    elif report["status"] == "warning":
        print("⚠️ Token mismatch detected!")
        print()
        print("The hardcoded token doesn't match what the native binary provides.")
        print()
        print("Quick fix:")
        print(f"   1. Open: Fusion-360-MCP-Server\\lib\\mcp_client.py")
        print(f"   2. Find line 227")
        print(f"   3. Replace with: self.auth_header = \"{report['native_token']}\"")
        print(f"   4. Save and restart Fusion add-in")
        print()
        print("Or better fix:")
        print(f"   1. Comment out lines 226-228 in mcp_client.py")
        print(f"   2. Let native binary provide the real token")
        print(f"   3. Save and restart Fusion add-in")

    elif report["status"] == "error":
        print("❌ Auth errors detected!")
        print()
        if not report["manifest_found"]:
            print("MCP-Link is not installed or manifest not found.")
            print()
            print("Fix:")
            print("   1. Download MCP-Link from https://aurafriday.com/")
            print("   2. Run the installer")
            print("   3. Run this test again")
        elif not report["binary_found"]:
            print("Native binary not found.")
            print()
            print("Fix:")
            print("   1. Uninstall MCP-Link completely")
            print("   2. Delete C:\\Users\\[YOU]\\AppData\\Local\\AuraFriday")
            print("   3. Reinstall MCP-Link")
            print("   4. Run this test again")
        elif report["native_token_error"]:
            print(f"Cannot get token from native binary: {report['native_token_error']}")
            print()
            print("Fix:")
            print("   1. Close Claude Desktop")
            print("   2. Close MCP-Link server (aura.exe)")
            print("   3. Start MCP-Link from Start menu")
            print("   4. Run this test again")
        else:
            print("Unknown error. Check the diagnostic output above.")

    print()
    print("=" * 70)
    print()

    # Return appropriate exit code
    exit_codes = {"ok": 0, "warning": 1, "error": 2, "unknown": 3}
    sys.exit(exit_codes.get(report["status"], 3))

except ImportError as e:
    print("ERROR: Cannot import auth_diagnostics module")
    print(f"Details: {e}")
    print()
    print("Make sure you're running this script from the project root:")
    print("  python test_mcp_auth.py")
    sys.exit(1)

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
