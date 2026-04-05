# Blocks writes to the deprecated mobile/ directory.
# Reads tool call JSON from stdin; outputs a deny decision if the target path is inside mobile/ (but not janmitra_mobile/).

$raw = [System.Console]::In.ReadToEnd()

try {
    $data = $raw | ConvertFrom-Json -ErrorAction Stop
}
catch {
    exit 0
}

$toolInput = $data.tool_input
if (-not $toolInput) { exit 0 }

$path = ""
if ($toolInput.PSObject.Properties["path"]) { $path = $toolInput.path }
elseif ($toolInput.PSObject.Properties["file_path"]) { $path = $toolInput.file_path }

if (-not $path) { exit 0 }

# Normalise separators
$normPath = $path -replace "\\", "/"

# Match paths that are inside mobile/ but NOT janmitra_mobile/
if ($normPath -match "(^|/)mobile/" -and $normPath -notmatch "janmitra_mobile") {
    $response = @{
        hookSpecificOutput = @{
            hookEventName            = "PreToolUse"
            permissionDecision       = "deny"
            permissionDecisionReason = "BLOCKED: 'mobile/' is deprecated. Use 'janmitra_mobile/' instead."
        }
    }
    $response | ConvertTo-Json -Depth 4 -Compress
    exit 0
}

exit 0
