# MCP Server Setup Improvements

## Current Issues

1. **Hardcoded auth token** - Causes intermittent failures
2. **Poor error messages** - Hard to diagnose connection issues
3. **No automatic recovery** - Manual restart required when auth fails

## Proposed Improvements

### Phase 1: Better Diagnostics (Quick Win)

**Goal:** Make it obvious what's wrong when connection fails

**Changes:**
1. Add detailed auth token diagnostics
2. Log both native binary token AND hardcoded token
3. Show clear error messages with recovery steps
4. Add connection health check endpoint

**Implementation:**
- Modify `mcp_client.py` to log both token values
- Add retry logic with better backoff
- Create diagnostic command in Fusion

### Phase 2: Dynamic Token Discovery (Proper Fix)

**Goal:** Use the ACTUAL token from native binary instead of hardcoded

**Changes:**
1. Remove hardcoded token workaround
2. Implement proper token refresh logic
3. Add fallback to token file if binary fails
4. Cache valid tokens between sessions

**Implementation:**
- Parse native binary output more carefully
- Add token validation before attempting connection
- Store last known good token in config file
- Retry with cached token if binary fails

### Phase 3: Simplified Setup (Best UX)

**Goal:** Make setup bulletproof for end users

**Changes:**
1. Auto-detect MCP-Link server issues
2. Show setup wizard on first run
3. Add "Test Connection" button in Fusion
4. Generate troubleshooting report automatically

**Implementation:**
- Create setup UI panel in Fusion
- Add connection status indicator
- One-click diagnostics export
- Guided troubleshooting workflow

## Recommended Approach

**For immediate testing (what you need now):**
1. Implement Phase 1 (better diagnostics)
2. Add manual "Reconnect with fresh token" command
3. Log all connection attempts with timestamps

**For long-term reliability:**
1. Complete Phase 2 (dynamic tokens)
2. Add automated tests for connection flow
3. Document setup process clearly

## Quick Fix for Testing Phase 5-2

**Option A: Manual Token Update**
1. Get the REAL token from MCP-Link server logs
2. Update the hardcoded value to match
3. Restart Fusion add-in
4. Test Phase 5-2

**Option B: Token Discovery Debug Mode**
1. Enable verbose logging in config.py
2. Comment out hardcoded token override
3. Let native binary provide token
4. Check if that works better

**Option C: Direct Connection Mode**
1. Bypass native binary discovery
2. Connect directly to known server URL/port
3. Use token from config file
4. Skip auto-discovery that's failing

## Implementation Priority

**This Week (Unblock Testing):**
- [ ] Add better auth diagnostics
- [ ] Create manual reconnect command
- [ ] Document actual vs expected token values
- [ ] Add connection status to Text Commands

**Next Week (Proper Fix):**
- [ ] Implement dynamic token discovery
- [ ] Remove hardcoded workaround
- [ ] Add token validation
- [ ] Test with server restarts

**Future (Polish):**
- [ ] Setup wizard UI
- [ ] Connection health monitoring
- [ ] Auto-recovery from failures
- [ ] End-user documentation

## Testing Checklist

After implementing improvements:
- [ ] Fresh install connects successfully
- [ ] Connection survives server restart
- [ ] Clear error messages when auth fails
- [ ] Manual reconnect works
- [ ] No hardcoded tokens remain
- [ ] Works across multiple machines

## Success Criteria

Setup is "easy" when:
1. First-time setup takes < 5 minutes
2. Connection issues show clear error messages
3. Users can fix issues without reading code
4. 95%+ success rate on fresh installs
5. Automatic recovery from transient failures
