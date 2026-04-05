#!/usr/bin/env bash
# Blocks writes to the deprecated mobile/ directory.
# Reads tool call JSON from stdin; outputs a deny decision if path is inside mobile/ (but not janmitra_mobile/).

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    ti = d.get('tool_input', {})
    print(ti.get('path') or ti.get('file_path') or '')
except Exception:
    print('')
" 2>/dev/null)

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Normalise backslashes
NORM_PATH=$(echo "$FILE_PATH" | sed 's|\\|/|g')

# Match paths inside mobile/ but NOT janmitra_mobile/
if echo "$NORM_PATH" | grep -qE "(^|/)mobile/" && ! echo "$NORM_PATH" | grep -q "janmitra_mobile"; then
    echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"BLOCKED: mobile/ is deprecated. Use janmitra_mobile/ instead."}}'
    exit 0
fi

exit 0
