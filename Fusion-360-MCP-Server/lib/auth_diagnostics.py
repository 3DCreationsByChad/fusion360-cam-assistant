# -*- coding: utf-8 -*-
"""
Auth Diagnostics Module
Helps diagnose MCP connection and authentication issues
"""

import json
import platform
import subprocess
import struct
from pathlib import Path

def get_native_manifest_path():
    """Find the native messaging manifest file."""
    system_name = platform.system().lower()

    if system_name == "windows":
        import os
        appdata_local = os.environ.get('LOCALAPPDATA')
        if appdata_local:
            return Path(appdata_local) / "AuraFriday" / "com.aurafriday.shim.json"

    return None

def read_manifest(manifest_path):
    """Read the manifest file."""
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return None

def get_token_from_native_binary(manifest):
    """Run native binary and extract the auth token."""
    binary_path = manifest.get('path')
    if not binary_path or not Path(binary_path).exists():
        return None, "Binary not found"

    try:
        creation_flags = 0
        if platform.system() == 'Windows':
            try:
                creation_flags = subprocess.CREATE_NO_WINDOW
            except AttributeError:
                pass

        proc = subprocess.Popen(
            [str(binary_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=False,
            bufsize=0,
            creationflags=creation_flags
        )

        # Read 4-byte length prefix
        length_bytes = proc.stdout.read(4)
        if len(length_bytes) != 4:
            proc.terminate()
            return None, "Failed to read length prefix"

        message_length = struct.unpack('<I', length_bytes)[0]

        # Read JSON payload
        json_bytes = proc.stdout.read(message_length)
        proc.terminate()

        if len(json_bytes) < message_length:
            # Partial read - try to extract what we can
            text = json_bytes.decode('utf-8', errors='ignore')
        else:
            text = json_bytes.decode('utf-8')

        try:
            config_json = json.loads(text)

            # Extract token
            mcp_servers = config_json.get('mcpServers', {})
            if mcp_servers:
                first_server = next(iter(mcp_servers.values()), None)
                if first_server and 'headers' in first_server:
                    auth_header = first_server['headers'].get('Authorization')
                    return auth_header, None

            return None, "No auth header in config"

        except json.JSONDecodeError:
            # Try regex extraction
            import re
            auth_match = re.search(r'"Authorization"\s*:\s*"(Bearer\s+[^"]+)"', text)
            if auth_match:
                return auth_match.group(1), None
            return None, "Failed to parse JSON and extract token"

    except Exception as e:
        return None, str(e)

def get_hardcoded_token():
    """Return the hardcoded workaround token."""
    return "Bearer 1816a663-12dd-4868-9658-e0bd65154d9e"

def diagnose_auth():
    """
    Run complete auth diagnostics and return report.

    Returns:
        dict with diagnostic information
    """
    report = {
        "status": "unknown",
        "manifest_found": False,
        "manifest_path": None,
        "binary_found": False,
        "binary_path": None,
        "native_token": None,
        "native_token_error": None,
        "hardcoded_token": None,
        "tokens_match": False,
        "recommendation": None
    }

    # Step 1: Find manifest
    manifest_path = get_native_manifest_path()
    report["manifest_path"] = str(manifest_path) if manifest_path else None

    if not manifest_path or not manifest_path.exists():
        report["status"] = "error"
        report["recommendation"] = "MCP-Link not installed. Install from https://aurafriday.com/"
        return report

    report["manifest_found"] = True

    # Step 2: Read manifest
    manifest = read_manifest(manifest_path)
    if not manifest:
        report["status"] = "error"
        report["recommendation"] = "Manifest file corrupted. Reinstall MCP-Link."
        return report

    binary_path = manifest.get('path')
    report["binary_path"] = binary_path

    if not binary_path or not Path(binary_path).exists():
        report["status"] = "error"
        report["recommendation"] = "Native binary not found. Reinstall MCP-Link."
        return report

    report["binary_found"] = True

    # Step 3: Get token from native binary
    native_token, error = get_token_from_native_binary(manifest)
    report["native_token"] = native_token
    report["native_token_error"] = error

    # Step 4: Compare with hardcoded token
    hardcoded = get_hardcoded_token()
    report["hardcoded_token"] = hardcoded

    if native_token and hardcoded:
        report["tokens_match"] = (native_token == hardcoded)

    # Step 5: Determine status and recommendation
    if native_token and native_token == hardcoded:
        report["status"] = "ok"
        report["recommendation"] = "Auth tokens match. Connection should work."
    elif native_token and native_token != hardcoded:
        report["status"] = "warning"
        report["recommendation"] = f"Token mismatch! Update hardcoded token in mcp_client.py line 227 to:\n{native_token}"
    elif not native_token and error:
        report["status"] = "error"
        report["recommendation"] = f"Cannot get token from native binary: {error}\nUsing hardcoded fallback, which may not work."
    else:
        report["status"] = "error"
        report["recommendation"] = "Unknown auth issue. Check MCP-Link server is running."

    return report

def format_report(report):
    """Format diagnostic report as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("MCP AUTH DIAGNOSTICS")
    lines.append("=" * 60)
    lines.append("")

    status_icon = {
        "ok": "✅",
        "warning": "⚠️",
        "error": "❌",
        "unknown": "❓"
    }.get(report["status"], "?")

    lines.append(f"Status: {status_icon} {report['status'].upper()}")
    lines.append("")

    lines.append("MANIFEST:")
    lines.append(f"  Found: {'✅' if report['manifest_found'] else '❌'}")
    lines.append(f"  Path: {report['manifest_path']}")
    lines.append("")

    lines.append("NATIVE BINARY:")
    lines.append(f"  Found: {'✅' if report['binary_found'] else '❌'}")
    lines.append(f"  Path: {report['binary_path']}")
    lines.append("")

    lines.append("AUTH TOKENS:")
    lines.append(f"  Native Token:    {report['native_token'][:50] + '...' if report['native_token'] else 'NOT AVAILABLE'}")
    if report['native_token_error']:
        lines.append(f"  Error:           {report['native_token_error']}")
    lines.append(f"  Hardcoded Token: {report['hardcoded_token'][:50]}...")
    lines.append(f"  Match:           {'✅ YES' if report['tokens_match'] else '❌ NO'}")
    lines.append("")

    lines.append("RECOMMENDATION:")
    for line in report['recommendation'].split('\n'):
        lines.append(f"  {line}")
    lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)

if __name__ == "__main__":
    # Run diagnostics
    report = diagnose_auth()
    print(format_report(report))

    # Return exit code based on status
    exit_codes = {"ok": 0, "warning": 1, "error": 2, "unknown": 3}
    exit(exit_codes.get(report["status"], 3))
