param(
    [Parameter(Mandatory = $false)]
    [string]$PyPIToken,
    
    [Parameter(Mandatory = $false)]
    [switch]$DryRun
)

# Build and publish origin-or to PyPI
$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$PYTHON = "C:\Users\smile\AppData\Local\Programs\Python\Python313\python.exe"
$TWINE = "C:\Users\smile\AppData\Local\Programs\Python\Python313\Scripts\twine.exe"

# Read version from setup.py
$VERSION = (Select-String -Path "$ROOT\setup.py" -Pattern 'version="(.+?)"').Matches[0].Groups[1].Value
Write-Host "Publishing origin-or v$VERSION to PyPI..." -ForegroundColor Cyan

# Build
Write-Host "Building package..." -ForegroundColor Yellow
Remove-Item -Recurse -Force "$ROOT\dist\*" -ErrorAction SilentlyContinue
& $PYTHON -m build --outdir "$ROOT\dist" "$ROOT"
if (-not $?) { throw "Build failed" }
Write-Host "Build successful!" -ForegroundColor Green

if ($DryRun) { Write-Host "Dry run — skipping upload. Run without -DryRun to publish." -ForegroundColor Yellow; return }

# Upload
$env:TWINE_USERNAME = "__token__"
$env:TWINE_PASSWORD = $PyPIToken
if (-not $env:TWINE_PASSWORD) { throw "Provide -PyPIToken parameter or set TWINE_PASSWORD environment variable" }

& $TWINE upload "$ROOT\dist\origin_or-$VERSION-py3-none-any.whl" "$ROOT\dist\origin_or-$VERSION.tar.gz"
Write-Host "Published origin-or v$VERSION!" -ForegroundColor Green
