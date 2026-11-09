# Development-only Windows x64/Python 3.12 bundle installer.
# This reproduces tested dependencies; it does NOT approve them for production.
$ErrorActionPreference = 'Stop'
$bundle = Split-Path -Parent $PSScriptRoot
$wheelDir = Join-Path $bundle 'wheels'
$requirements = Join-Path $bundle 'requirements-development.txt'
$venv = Join-Path $bundle '.venv'
if (!(Test-Path $requirements) -or !(Test-Path $wheelDir)) {
    throw 'Run this script from an extracted development bundle containing requirements-development.txt and wheels/.'
}
if (Test-Path $venv) {
    throw 'The bundle already contains .venv. Use a new extraction directory; existing environments will not be overwritten.'
}
Write-Warning 'Development reproduction only. SDK/pyasn1 release-policy conflict remains open; do not deploy this environment to production.'
& py -3.12 (Join-Path $PSScriptRoot 'verify_delivery.py') --bundle $bundle
if ($LASTEXITCODE -ne 0) { throw 'Environment or package verification failed. Use Windows x64/Python 3.12 and an unmodified fresh extraction.' }
& py -3.12 -m venv $venv
if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
$python = Join-Path $venv 'Scripts\python.exe'
& $python -m pip install --no-index --find-links $wheelDir -r $requirements 'huaweicloud-mcp-core==1.0.0' 'mcp_server_supabase==0.3.8a2'
if ($LASTEXITCODE -ne 0) { throw 'Offline installation failed; retain the error locally and do not bypass dependency checks.' }
& $python -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Installed dependency metadata is inconsistent.' }
& $python -m mcp_server_supabase.diagnostics offline
if ($LASTEXITCODE -ne 0) { throw 'Offline MCP diagnostics failed.' }
Write-Host 'Development installation completed. No cloud API was called. Review WORKSTATION.md before authorized cloud reads.'
