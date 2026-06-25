# Origin Language Secure Installer
# This script installs origin.exe and includes protections against common attack vectors.

$installDir = "$HOME\.origin\bin"
$exeName = "origin.exe"
$sourcePath = Join-Path $PSScriptRoot $exeName

# ==============================================================================
# SECURITY: 1. BINARY SWAPPING PROTECTION (Checksum Verification)
# We hardcode the exact SHA-256 hash of the legitimate origin.exe.
# If an attacker replaces origin.exe with a virus in the zip file, the hash
# will change, and this script will refuse to install it.
# ==============================================================================
$expectedHash = "99ABF86F3282120A8CE74EC04E2634F284C48642955A0AF58FBD0BD6BA2E1CBB"

Write-Host "--- Secure Origin Language Installer ---" -ForegroundColor Cyan

# Check if source exists
if (-not (Test-Path $sourcePath)) {
    Write-Host "Error: Could not find $exeName in this folder." -ForegroundColor Red
    Pause
    exit
}

# Verify the binary integrity
Write-Host "[*] Verifying origin.exe integrity against tampering..." -ForegroundColor Cyan
$actualHash = (Get-FileHash -Path $sourcePath -Algorithm SHA256).Hash

if ($actualHash -ne $expectedHash) {
    Write-Host "`n[!!!] CRITICAL SECURITY ALERT [!!!]" -ForegroundColor Red -BackgroundColor Black
    Write-Host "The origin.exe file has been modified, corrupted, or replaced!" -ForegroundColor Red
    Write-Host "This is a sign of a potential Binary Swapping attack (Trojan)." -ForegroundColor Yellow
    Write-Host "Installation aborted. Please download a fresh, official copy."
    Pause
    exit
}
Write-Host "[+] Binary integrity verified successfully." -ForegroundColor Green


# 2. Create install directory
if (-not (Test-Path $installDir)) {
    Write-Host "[*] Creating installation directory: $installDir"
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
}

# 3. Copy binary
Write-Host "[*] Installing Origin to $installDir..."
Copy-Item $sourcePath -Destination $installDir -Force


# ==============================================================================
# SECURITY: 2. PATH HIJACKING PROTECTION (Prepend instead of Append)
# We add the install directory to the *FRONT* of the PATH variable.
# If an attacker places a fake 'origin.exe' in C:\Windows (which is in the PATH),
# Windows will still run our legitimate version first because our folder 
# is evaluated before the Windows folder.
# ==============================================================================
Write-Host "[*] Securing system PATH..."
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")

# Clean up path to prevent issues
$cleanPath = if ([string]::IsNullOrWhiteSpace($currentPath)) { "" } else { $currentPath.Trim(';') }

if ($cleanPath -notlike "*$installDir*") {
    # Notice we put $installDir BEFORE $cleanPath
    $newPath = if ($cleanPath -eq "") { $installDir } else { "$installDir;$cleanPath" }
    
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    $env:Path = "$installDir;" + $env:Path # Update current session
    Write-Host "[+] Successfully secured and added to PATH!" -ForegroundColor Green
} else {
    Write-Host "[!] Origin is already in your PATH." -ForegroundColor Yellow
}

Write-Host "`n--- Installation Complete! ---" -ForegroundColor Green
Write-Host "You can now type 'origin' to start."
Pause
