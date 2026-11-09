# Local client entry; intentionally no execution-policy bypass or global settings changes.
param([switch]$NoLaunch)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
    throw 'This delivery supports Windows x64 only.'
}
$claudeCommand = Get-Command claude -ErrorAction SilentlyContinue
if (!$NoLaunch -and !$claudeCommand) { throw 'Install and sign in to Claude Code first, then run this same command.' }
if (!$env:LOCALAPPDATA) { throw 'LOCALAPPDATA is missing.' }
$bundle = $PSScriptRoot
# Validate payload before running shipped executables or Python code.
$manifest = Get-Content -LiteralPath (Join-Path $bundle 'DELIVERY.json') -Raw | ConvertFrom-Json
foreach ($entry in $manifest.PSObject.Properties) {
    $relative = $entry.Name
    if ($relative -match '(^/|(^|/)\.\.(/|$)|:|\\)' -or $entry.Value -notmatch '^[0-9a-f]{64}$') { throw 'Invalid delivery manifest.' }
    $file = Join-Path $bundle $relative
    if (!(Test-Path -LiteralPath $file -PathType Leaf)) { throw "Missing delivery file: $relative" }
    if ((Get-Item -LiteralPath $file).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked payload is not allowed.' }
    if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) { throw "Delivery checksum mismatch: $relative" }
}
$root = Join-Path $env:LOCALAPPDATA 'HuaweiCloudSupabaseLocal'
New-Item -ItemType Directory -Force $root | Out-Null
$lock = $null
try {
    $lock = [IO.File]::Open((Join-Path $root 'setup.lock'), [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    # These variables affect only this installer process and its children.
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $root 'python'
    $env:UV_CACHE_DIR = Join-Path $root 'cache'
    $env:UV_PYTHON_INSTALL_BIN = 'false'
    $env:UV_PYTHON_INSTALL_REGISTRY = 'false'
    $uv = Join-Path $bundle 'uv.exe'
    $runtime = Join-Path $root 'runtime'
    $python = Join-Path $runtime 'Scripts\python.exe'
    if (!(Test-Path -LiteralPath $python)) {
        if (Test-Path -LiteralPath $runtime) { throw 'Incomplete runtime exists. Preserve it and report the failure; it will not be overwritten.' }
        & $uv --no-config venv --no-project --python 3.12.10 $runtime
        if ($LASTEXITCODE -ne 0) { throw 'Python preparation failed. Check approved network access; do not disable TLS.' }
    }
    & $python -I (Join-Path $bundle 'setup_client.py') --bundle $bundle --root $root
    if ($LASTEXITCODE -ne 0) { throw 'Local installation failed. Claude was not started; preserve the error and existing state.' }
} finally {
    if ($lock) { $lock.Dispose() }
}
Write-Host "Local MCP + Skill ready (read-only). Workspace: $root\workspace"
Write-Host 'Existing cloud test environments and their ledgers are not migrated. No cloud API was called by installation.'
if (!$NoLaunch) {
    Push-Location (Join-Path $root 'workspace')
    try {
        & $claudeCommand.Source --strict-mcp-config --mcp-config (Join-Path $root 'workspace\.mcp.json') 'Load the huaweicloud-supabase Skill and describe the available scenarios. Do not call any business cloud API until I request it.'
        if ($LASTEXITCODE -ne 0) { throw 'Claude exited with an error; the installed environment has been retained.' }
    } finally { Pop-Location }
}
