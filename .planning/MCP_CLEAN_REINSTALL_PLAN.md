# MCP-Link Clean Reinstall Plan

**Use this plan if simple restarts don't fix the fusion360 tool registration issue.**

**Problem:** fusion360 tool not visible in Claude Desktop despite MCP-Link server running and Fusion add-in installed.

**Root Cause:** Likely OAuth/authentication misconfiguration between Claude Desktop ↔ MCP-Link server ↔ Fusion add-in.

**Solution:** Complete clean reinstall of MCP-Link to reset all authentication and configuration.

---

## ⚠️ Before You Start

### Backup Current State

1. **Document current configuration:**
   ```bash
   # Copy current Claude Desktop config
   copy "%APPDATA%\Claude\claude_desktop_config.json" "%USERPROFILE%\Desktop\claude_config_backup.json"
   ```

2. **Note current MCP-Link server port:**
   - Currently running on: `localhost:31173`
   - Save this info in case you need it

3. **Verify Fusion add-in junction is intact:**
   ```bash
   dir "C:\Users\cdeit\AppData\Roaming\Autodesk\ApplicationPlugins\MCP-link.bundle\Contents"
   ```
   - Should show: `Contents -> C:\Users\cdeit\fusion360-cam-assistant\Fusion-360-MCP-Server`
   - ✅ This junction will NOT be affected by MCP-Link reinstall

---

## 🗑️ Step 1: Clean Uninstall

### 1A. Close All Applications

```bash
# Close Claude Desktop completely
taskkill /IM "Claude.exe" /F

# Kill MCP-Link server
taskkill /IM "aura.exe" /F

# Fusion 360 can stay open (we'll just stop the add-in)
```

In Fusion 360:
- Tools > Add-Ins > Scripts and Add-Ins
- Select "MCP-Link"
- Click **Stop**
- Leave Fusion 360 open

### 1B. Uninstall MCP-Link Application

**Option A: If installed via installer:**
1. Windows Settings > Apps > Installed apps
2. Search for "MCP-Link" or "Aura"
3. Click Uninstall
4. Follow prompts

**Option B: If installed via portable/manual:**
1. Find MCP-Link installation directory
2. Run uninstaller if present
3. Or manually delete the directory

**Option C: If installed via npm/npx:**
```bash
# Check if it's a global npm package
npm list -g | findstr mcp

# If found, uninstall
npm uninstall -g mcp-link
npm uninstall -g @aurafriday/mcp-link
```

### 1C. Clean Configuration Files

```bash
# Remove MCP-Link data directories (if they exist)
rmdir /S /Q "%APPDATA%\Aura"
rmdir /S /Q "%LOCALAPPDATA%\Aura"
rmdir /S /Q "%APPDATA%\mcp-link"
rmdir /S /Q "%LOCALAPPDATA%\mcp-link"

# Remove Claude Desktop MCP cache (optional, forces re-discovery)
rmdir /S /Q "%APPDATA%\Claude\mcp_cache"
```

### 1D. Verify Clean State

```bash
# No aura.exe should be running
tasklist | findstr /I "aura"

# No MCP-Link server listening
netstat -ano | findstr "31173"
```

Both should return nothing.

---

## 📥 Step 2: Fresh Install

### 2A. Download Latest MCP-Link

1. Visit: https://aurafriday.com/
2. Download the **Windows installer**
3. Save to: `%USERPROFILE%\Downloads\mcp-link-installer.exe`

### 2B. Install MCP-Link

1. Run the installer
2. Accept default installation location
3. **Important:** During setup, note:
   - Installation directory
   - Auto-start option (enable if available)
   - Port number (should auto-select)

4. Complete installation

### 2C. Verify MCP-Link Server is Running

```bash
# Check if aura.exe is running
tasklist | findstr /I "aura"

# Should show: aura.exe with a process ID

# Check what port it's using
netstat -ano | findstr "LISTENING" | findstr "<PID>"
```

Take note of the port (e.g., `31173` or different).

---

## ⚙️ Step 3: Configure Claude Desktop

### 3A. Update Claude Desktop MCP Configuration

**Check if MCP-Link auto-configured:**

```bash
type "%APPDATA%\Claude\claude_desktop_config.json"
```

**Expected:** Should have `mypc` and possibly `fusion360` or `mcp-link` entries.

**If missing or incorrect, manually add:**

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mypc": {
      "command": "C:\\Users\\cdeit\\.claude\\mcp-mypc.bat",
      "args": []
    }
  },
  "preferences": {
    "coworkScheduledTasksEnabled": false,
    "sidebarMode": "chat"
  }
}
```

**Note:** MCP-Link might auto-configure itself via native messaging. If so, you may not need to manually add it.

### 3B. Restart Claude Desktop

```bash
# Start Claude Desktop
start "" "%LOCALAPPDATA%\AnthropicClaude\Claude.exe"
```

Or launch from Start menu.

---

## 🔗 Step 4: Reconnect Fusion Add-in

### 4A. Restart Fusion Add-in

In Fusion 360:
1. Tools > Add-Ins > Scripts and Add-Ins
2. Find "MCP-Link"
3. Click **Run**
4. **Watch the Text Commands window carefully**

### 4B. Monitor Connection Messages

Open: View > Text Commands (Ctrl+Shift+`)

**Look for:**

✅ **Success messages:**
```
MCP: Discovering native messaging host...
MCP: Found server at https://127.0.0.1:31173
MCP: Connecting to server...
MCP: Connected successfully
MCP: Registered tool 'fusion360'
```

❌ **Error messages:**
```
MCP: Native messaging discovery failed
MCP: Connection failed - [reason]
MCP: OAuth authentication failed
```

**If errors appear:** Copy the FULL error message for debugging.

### 4C. Verify in Claude Desktop

In Claude Desktop, ask:
```
List all available MCP tools
```

**Expected result:**
- ✅ Should see `fusion360` tool in the list
- ✅ Should see operations like `record_user_choice`, `get_feedback_stats`, etc.

---

## ✅ Step 5: Verification Tests

### Test 1: Fusion360 Tool Visible

In Claude Desktop:
```
What operations are available for the fusion360 tool?
```

Should list all operations including Phase 5 learning operations.

### Test 2: Basic Operation Works

```
Get CAM state from Fusion 360
```

Should return current Fusion 360 state without errors.

### Test 3: Phase 5 Operation Works

```
Call get_feedback_stats for Fusion 360
```

Should return empty stats (no feedback recorded yet) but no errors.

---

## 🔥 Troubleshooting

### Issue: fusion360 tool still not visible after reinstall

**Possible causes:**

1. **MCP-Link server not running:**
   ```bash
   tasklist | findstr /I "aura"
   ```
   - If not running, launch MCP-Link from Start menu

2. **Fusion add-in not connecting:**
   - Check Text Commands for errors
   - Verify `MCP_AUTO_CONNECT = True` in config.py
   - Try manual connection (if there's a "Connect to MCP" button)

3. **OAuth/authentication still failing:**
   - Check MCP-Link server logs (location varies by install)
   - May need to check MCP-Link documentation for auth setup

4. **Port conflict:**
   - Check if port 31173 is blocked by firewall
   - Check if another app is using the port

### Issue: Text Commands shows connection errors

**"Native messaging discovery failed":**
- MCP-Link server might not be registered in Windows registry
- Reinstall MCP-Link with admin privileges
- Check if native messaging manifest exists

**"OAuth authentication failed":**
- MCP-Link server authentication token issue
- Check MCP-Link server settings/dashboard
- May need to reset authentication token

**"Connection refused":**
- MCP-Link server not running on expected port
- Check actual port with `netstat -ano | findstr "aura"`
- Update Fusion add-in config if port changed

---

## 🔄 Rollback Plan (If Things Go Wrong)

### Restore Previous State

1. **Restore Claude Desktop config:**
   ```bash
   copy "%USERPROFILE%\Desktop\claude_config_backup.json" "%APPDATA%\Claude\claude_desktop_config.json"
   ```

2. **Fusion add-in is safe:**
   - The code is unaffected (lives in git repo)
   - Junction is unaffected
   - Just stop/start the add-in as needed

3. **Reinstall previous MCP-Link version:**
   - If you have the old installer, run it
   - Or wait for next MCP-Link update

---

## 📊 Success Criteria

After completing this plan, you should have:

- ✅ MCP-Link server (aura.exe) running
- ✅ Fusion add-in connected to MCP-Link
- ✅ `fusion360` tool visible in Claude Desktop
- ✅ All Phase 5 operations callable:
  - `record_user_choice`
  - `get_feedback_stats`
  - `export_feedback_history`
  - `clear_feedback_history`
- ✅ Ready to run Phase 5 testing guide

---

## 📝 Notes for Future Reference

**Current Setup (before reinstall):**
- MCP-Link server running on port: 31173
- Fusion add-in junction: Working
- Phase 5 code: Deployed
- Issue: OAuth/registration failure

**After Reinstall:**
- Document new port if changed: __________
- Document any configuration changes: __________
- Note any additional setup steps needed: __________

---

## 🆘 If This Plan Doesn't Work

If after clean reinstall the fusion360 tool STILL doesn't appear:

1. **Check MCP-Link documentation:**
   - Visit: https://github.com/AuraFriday/mcp-link
   - Look for: Setup guides, troubleshooting, issues

2. **Alternative approach - Direct MCP Server:**
   - Consider running Fusion add-in as a standalone MCP server
   - Configure Claude Desktop to connect directly
   - Bypass MCP-Link middleman (requires custom setup)

3. **File GitHub issue:**
   - Repository: AuraFriday/mcp-link
   - Include: Error logs, OS version, MCP-Link version
   - Title: "fusion360 tool not registering with Claude Desktop"

---

**Plan created:** 2026-02-06
**Use case:** Resolve fusion360 tool registration issues
**Expected time:** 30-45 minutes
**Risk level:** Low (Fusion add-in code is safe in git repo)

---

**Good luck! 🍀 Try the simple restart first - this plan is your nuclear option if needed.**
