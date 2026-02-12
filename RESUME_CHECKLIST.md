# Quick Resume Checklist ✅

**When you come back, do these in order:**

## 1️⃣ Fusion 360 (2 minutes)

- [ ] Open Fusion 360
- [ ] Tools > Add-Ins > Scripts and Add-Ins
- [ ] Find "MCP-Link" → Click **Stop**, then **Run**
- [ ] View > Text Commands (Ctrl+Shift+`)
- [ ] Look for: `[SUCCESS] fusion360 registered successfully!`

**If you see errors:** Note them and check `TROUBLESHOOTING_AUTH.md`

---

## 2️⃣ Check MCP-Link Server (1 minute)

- [ ] Open MCP-Link server dashboard
- [ ] Check: **Network Tools** count
- [ ] Should show: **1** (fusion360 tool)

**If still 0:** Fusion didn't connect - check Fusion Text Commands for errors

---

## 3️⃣ Claude Desktop (3 minutes)

- [ ] **Close** Claude Desktop completely (Task Manager if needed)
- [ ] Run: `rmdir /S /Q "%APPDATA%\Claude\mcp_cache"`
- [ ] **Restart** Claude Desktop
- [ ] Wait 10 seconds for initialization

---

## 4️⃣ Test Connection (2 minutes)

**In Claude Desktop, type:**
```
List all available MCP tools
```

**Should see:**
- `mcp-link` server
- Tools from MCP-Link (including fusion360 if connected)

**Then test:**
```
Get CAM state from Fusion 360
```

**If it works:** 🎉 Everything is connected!

---

## ✅ Success = All Green

- ✅ Fusion shows "SUCCESS" message
- ✅ Server shows "Network Tools: 1"
- ✅ Claude lists MCP tools
- ✅ Claude can call Fusion operations

---

## 🆘 If Something's Wrong

1. Check: `SESSION_STATUS.md` (full details)
2. Check: `TROUBLESHOOTING_AUTH.md` (specific fixes)
3. Run: `python test_mcp_auth.py` (diagnose auth)

---

**Total time to resume: ~10 minutes**

**Next after this works:** Test Phase 5-2 operations! 🚀
