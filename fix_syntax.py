#!/usr/bin/env python3
"""Fix missing closing parens in feedback_store.py"""

import re

file_path = "Fusion-360-MCP-Server/feedback_learning/feedback_store.py"

# Read file
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern: _unwrap_mcp_result(mcp_call_func(...))
# The issue is that lines with `        })` after an `_unwrap_mcp_result(mcp_call_func(` call
# should have an extra `)` to close the `_unwrap_mcp_result(`

# Find all instances of the pattern and fix them
# This is a multi-line pattern, so we'll do it line by line

lines = content.split('\n')
fixed_lines = []
in_unwrap_call = False
unwrap_start_line = -1

for i, line in enumerate(lines):
    # Check if we're starting an _unwrap_mcp_result call
    if '_unwrap_mcp_result(mcp_call_func' in line and '=' in line:
        in_unwrap_call = True
        unwrap_start_line = i
        fixed_lines.append(line)
    # Check if we're at the closing of the mcp_call_func
    elif in_unwrap_call and line.strip() == '})':
        # Add extra closing paren
        fixed_lines.append(line + ')')
        in_unwrap_call = False
    else:
        fixed_lines.append(line)

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(fixed_lines))

print(f"Fixed {len([l for l in fixed_lines if l.endswith('})')])} instances")
