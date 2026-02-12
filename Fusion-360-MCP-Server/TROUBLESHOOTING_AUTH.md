# MCP Auth Troubleshooting Guide

## Quick Diagnosis

The add-in now **automatically runs auth diagnostics** when it starts.

### View Diagnostics

1. Open Fusion 360
2. Tools > Add-Ins > Stop/Run the MCP-Link add-in
3. Open **Text Commands** window (Ctrl+Shift+`)
4. Look for the diagnostics report

### What the Diagnostics Show

```
MCP AUTH DIAGNOSTICS
====================================
Status: ✅ OK / ⚠️ WARNING / ❌ ERROR

MANIFEST:
  Found: ✅/❌
  Path: C:\Users\...\com.aurafriday.shim.json

NATIVE BINARY:
  Found: ✅/❌
  Path: C:\...\aura.exe

AUTH TOKENS:
  Native Token:    Bearer 1816a663-12dd-4868-9658-e0bd65154d9e...
  Hardcoded Token: Bearer 1816a663-12dd-4868-9658-e0bd65154d9e...
  Match:           ✅ YES / ❌ NO

RECOMMENDATION:
  [What to do next]
```

## Common Issues & Fixes

### ❌ ERROR: MCP-Link not installed

**Symptoms:**
- Manifest not found
- Status shows ERROR

**Fix:**
1. Download MCP-Link from https://aurafriday.com/
2. Run the installer
3. Restart Fusion add-in

### ⚠️ WARNING: Token mismatch

**Symptoms:**
- Tokens don't match
- Connection sometimes works, sometimes fails

**Fix:**
```python
# Option A: Update hardcoded token (quick)
# Edit: Fusion-360-MCP-Server\lib\mcp_client.py line 227
# Replace with the token shown in diagnostics:
self.auth_header = "Bearer [PASTE TOKEN HERE]"

# Option B: Remove hardcoded workaround (better)
# Comment out lines 226-228 in mcp_client.py:
# #self.auth_header = "Bearer 1816a663-12dd-4868-9658-e0bd65154d9e"
# #self.log("[WORKAROUND] Using hardcoded valid token", force=True)

# Then let native binary provide the real token
```

### ❌ ERROR: Native binary not found

**Symptoms:**
- Binary path shows but file doesn't exist
- MCP-Link crashed or uninstalled incorrectly

**Fix:**
1. Completely uninstall MCP-Link
2. Delete: `C:\Users\[YOU]\AppData\Local\AuraFriday`
3. Reinstall MCP-Link
4. Restart Fusion add-in

### ❌ ERROR: Cannot get token from native binary

**Symptoms:**
- Native token shows "NOT AVAILABLE"
- Error message about JSON parsing

**Root Cause:**
Native binary has a bug where it sends truncated JSON when the message is too large.

**Fix Options:**

**Option 1: Use hardcoded token (temporary)**
- Already in place (line 227)
- Update to match your server's token
- Not a long-term solution

**Option 2: Restart MCP-Link server**
```bash
# Close Claude Desktop
taskkill /IM "Claude.exe" /F

# Kill MCP-Link
taskkill /IM "aura.exe" /F

# Start MCP-Link from Start menu
# Restart Claude Desktop
# Restart Fusion add-in
```

**Option 3: Check server token manually**
1. Open MCP-Link server dashboard (if available)
2. Look for current auth token
3. Update line 227 in mcp_client.py
4. Restart add-in

## Testing Connection

After fixing auth issues:

1. **Restart the add-in:**
   - Tools > Add-Ins > Stop
   - Tools > Add-Ins > Run

2. **Check Text Commands for:**
   ```
   [SUCCESS] fusion360 registered successfully!
   Listening for reverse tool calls...
   ```

3. **Test in Claude Desktop:**
   ```
   List all available MCP tools
   ```
   - Should show `fusion360` tool

4. **Test a simple operation:**
   ```
   Get CAM state from Fusion 360
   ```

## Advanced: Manual Token Discovery

If diagnostics fail, manually extract the token:

```bash
# Windows Command Prompt:
cd C:\Users\cdeit\AppData\Local\AuraFriday

# Run the native binary and capture output:
aura.exe > token_output.txt 2>&1

# View the file - look for "Authorization": "Bearer ..."
notepad token_output.txt
```

## Prevention: Avoid Future Auth Issues

### Keep Tokens in Sync

**Option A: Store token in config file**
```python
# config.py
MCP_AUTH_TOKEN = "Bearer 1816a663-12dd-4868-9658-e0bd65154d9e"

# mcp_client.py
from .. import config
self.auth_header = config.MCP_AUTH_TOKEN
```

**Option B: Auto-refresh from native binary**
- Remove hardcoded token completely
- Always use fresh token from binary
- Add retry logic if binary fails

**Option C: Cache last known good token**
```python
# Save successful token to file
# Retry with cached token if binary fails
# Fall back to native binary on new failures
```

## When to File a Bug

File an issue if:
- Diagnostics show all green but connection still fails
- Token keeps changing without MCP-Link restart
- Native binary crashes when queried
- Auth works on one machine but not another

**Include in bug report:**
- Full diagnostic output
- MCP-Link version
- Windows version
- Complete error logs from Text Commands

## Quick Command Reference

```bash
# Check if MCP-Link is running
tasklist | findstr /I "aura"

# Check MCP-Link port
netstat -ano | findstr "LISTENING" | findstr "[PID]"

# Restart everything
taskkill /IM "Claude.exe" /F
taskkill /IM "aura.exe" /F
# Start MCP-Link from Start menu
# Start Claude Desktop
# Restart Fusion add-in
```

## Summary

**Most common issue:** Token mismatch
**Quick fix:** Update line 227 in mcp_client.py with actual token
**Long-term fix:** Remove hardcoded workaround, use native token
**Best practice:** Run diagnostics after every MCP-Link update

**The diagnostics run automatically now, so you'll always know what's wrong!**
