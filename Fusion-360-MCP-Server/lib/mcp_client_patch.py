# Patch for _connect_sse to add better error logging
# Line 690 replacement

except Exception as e:
  self.log(f"ERROR: Failed to connect to SSE: {e}", force=True)
  import traceback
  self.log(f"ERROR: Traceback:\n{traceback.format_exc()}", force=True)
  self.log(f"ERROR: Exception type: {type(e).__name__}", force=True)
  self.log(f"ERROR: Exception args: {e.args}", force=True)
  return None