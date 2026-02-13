# Beta Testing - Fusion 360 CAM Assistant

**Version:** v0.5.2-beta
**Release Name:** Feedback Learning System
**Status:** 🧪 Beta Testing
**Release Date:** February 12, 2026

## 🎯 What's Being Tested

The **feedback learning system** that enables AI to learn from your CAM workflow decisions:

✅ **Stock Preferences** - AI remembers your preferred stock offsets by material + geometry
✅ **Feedback Recording** - Track user choices and acceptance/rejection of AI suggestions
✅ **Statistics** - View learning progress with acceptance rates by operation/material/geometry
✅ **Persistent Storage** - All preferences saved to local SQLite databases

## 📋 Prerequisites

**REQUIRED:**
1. **MCP-Link Server** - Download from https://github.com/AuraFriday/mcp-link-server/releases/tag/latest
2. **Autodesk Fusion** - 2024 or later
3. **Claude.ai account** - For AI assistant access

## 🚀 Installation

### Step 1: Install MCP-Link Server
1. Download and install MCP-Link Server from the link above
2. Launch MCP-Link Server (should see icon in system tray)
3. Verify it's running at `https://127.0.0.1:31173`

### Step 2: Install Fusion Add-in

**Option A: Git Clone (Recommended for beta testers)**
```bash
git clone https://github.com/YOUR-USERNAME/fusion360-cam-assistant.git
cd fusion360-cam-assistant
```

**Option B: Download ZIP**
1. Download repository as ZIP
2. Extract to a folder

### Step 3: Load in Fusion
1. Open Autodesk Fusion
2. Press `Shift+S` → **Scripts and Add-Ins**
3. Click **Add-Ins** tab
4. Click green **+** button
5. Navigate to `Fusion-360-MCP-Server` folder
6. Click **Select Folder**
7. Click **Run** to start the add-in

### Step 4: Verify Connection
- Check Fusion Text Commands panel for "🔧 LOADING CONFIG.PY"
- Should see MCP connection established messages

## 🧪 Testing Scenarios

### Test 1: Stock Preference Learning
1. Open a design with simple geometry
2. Ask AI: "Set up stock for this aluminum part"
3. Accept or modify the suggestion
4. Ask AI: "What stock preferences do you have for aluminum + simple geometry?"
5. **Expected:** AI should remember your previous choice

### Test 2: Feedback Statistics
1. Make several CAM decisions (stock setup, toolpath strategy, etc.)
2. Ask AI: "Show me feedback statistics"
3. **Expected:** See breakdown by material, geometry type, operation type

### Test 3: Persistent Storage
1. Record some preferences/feedback
2. Close Fusion completely
3. Reopen Fusion and reload add-in
4. Ask AI: "What preferences do you have saved?"
5. **Expected:** Previous data still exists

## 🐛 Known Issues

- ⚠️ First-time schema initialization may be slow (creates database tables)
- ⚠️ Database files stored in: `%APPDATA%/Autodesk/Webservices/`
  - `cam_feedback.db` - Feedback history
  - `cam_preferences.db` - Stock preferences
  - `cam_strategy.db` - Toolpath strategy preferences
- ⚠️ Restart add-in after git pull to get latest code changes
- ⚠️ Error messages will appear in Text Commands panel (not UI popups)

## 📊 What to Report

Please report in Facebook group with this format:

```
**Test:** [Stock Preferences / Feedback Stats / etc.]
**Result:** [Success ✅ / Failed ❌]
**Issue:** [Description of problem]
**Logs:** [Paste relevant output from Text Commands panel]
**Environment:**
- Fusion Version: [e.g., 2024.2.1]
- OS: [Windows 11 / macOS / Linux]
- MCP-Link Version: [Check system tray icon]
```

## 🔄 Updating Beta Code

To get latest fixes:
```bash
cd fusion360-cam-assistant
git pull origin main
```

Then restart add-in in Fusion (Stop → Run).

## 💬 Support

- **GitHub Issues:** Fusion360-cam-assistant/issues
- **Direct Contact:** 3dcreationsbychad on Discord

## 🙏 Thank You!

Your beta testing helps make this tool production-ready. Every bug report and piece of feedback is valuable!

---

**Beta Tester Benefits:**
- 🎁 Early access to new features
- 🏆 Recognition in release notes
- 💪 Shape the product direction
- 🤝 Direct communication with developer
