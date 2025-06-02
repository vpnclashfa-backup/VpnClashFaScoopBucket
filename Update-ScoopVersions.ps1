# Update-ScoopVersions.ps1
[CmdletBinding()]
param (
    [Parameter(Mandatory=$false)]
    [string]$BucketPath = "./bucket",

    [Parameter(Mandatory=$true)] 
    [string]$ProvidedScoopShimsPath = "" 
)

Write-Output "Script Version: v7_final (Uses 'scoop' command after PATH modification)"
Write-Output "Provided BucketPath: $BucketPath"
Write-Output "Provided ScoopShimsPath: $ProvidedScoopShimsPath"

# Step 1: Validate the provided shims path and add it to this script's session PATH
if (-not [string]::IsNullOrWhiteSpace($ProvidedScoopShimsPath)) {
    Write-Output "Validating provided shims path: '$ProvidedScoopShimsPath'"
    if (Test-Path $ProvidedScoopShimsPath -PathType Container) {
        Write-Output "Provided shims path '$ProvidedScoopShimsPath' exists and is a directory."
        # Prepend the shims path to the current script's session PATH
        # This is crucial for PowerShell to find 'scoop' (which resolves to scoop.ps1 or scoop.cmd)
        if ($env:PATH -notlike "$ProvidedScoopShimsPath*") { # Add only if not already at the start (or present)
            $env:PATH = "$ProvidedScoopShimsPath;$($env:PATH)"
            Write-Output "SUCCESS: Prepended '$ProvidedScoopShimsPath' to this script's session PATH."
        } else {
            Write-Output "Provided shims path '$ProvidedScoopShimsPath' seems to be already in PATH."
        }
        Write-Output "Current script session PATH (first 200 chars): $($env:PATH.Substring(0, [System.Math]::Min($env:PATH.Length, 200)))..."
    } else {
        Write-Error "CRITICAL: Provided Scoop Shims Path '$ProvidedScoopShimsPath' does NOT exist or is not a directory. Cannot proceed."
        exit 1
    }
} else {
    Write-Error "CRITICAL: No ScoopShimsPath was provided to the script. This is required."
    exit 1
}

# Step 2: Verify 'scoop' command is now resolvable using Get-Command
Write-Output "--------------------------------------------------------------------"
Write-Output "Verifying 'scoop' command availability using Get-Command..."
$ScoopCmdInfo = Get-Command scoop -ErrorAction SilentlyContinue # Look for 'scoop' without extension
if ($ScoopCmdInfo) {
    Write-Output "SUCCESS: 'scoop' command resolved by Get-Command to: $($ScoopCmdInfo.Source) (Type: $($ScoopCmdInfo.CommandType))"
} else {
    Write-Error "CRITICAL FAILURE: 'scoop' command could NOT be resolved by Get-Command even after PATH modification. Cannot proceed."
    Write-Output "For debugging - Final PATH directories in this script's scope:"
    $env:PATH -split ';' | ForEach-Object { Write-Output "  - $_" }
    exit 1 
}

# Optional: Ensure SCOOP env var is set, and attempt module import
Write-Verbose "Ensuring \$env:SCOOP is sensible..."
$env:SCOOP = Split-Path $ProvidedScoopShimsPath 
Write-Output "Set \$env:SCOOP to: $($env:SCOOP)"
$ScoopModulePath = Join-Path $env:SCOOP "apps\scoop\current\modules\scoop.psm1"
if (Test-Path $ScoopModulePath) {
    try { Import-Module $ScoopModulePath -ErrorAction SilentlyContinue; Write-Verbose "Attempted Scoop module import."}
    catch { Write-Warning "Scoop module import failed: $($_.Exception.Message)"}
} else { Write-Verbose "Scoop module not found at '$ScoopModulePath'."}
Write-Output "--------------------------------------------------------------------"

$ManifestFiles = Get-ChildItem -Path $BucketPath -Filter "*.json" -File -ErrorAction SilentlyContinue
if (-not $ManifestFiles) {
    Write-Warning "No manifest files (.json) found in '$BucketPath'."
    exit 0 
}

$GlobalSuccess = $true 
foreach ($ManifestFile in $ManifestFiles) {
    $AppName = $ManifestFile.BaseName
    Write-Output "" 
    Write-Output "Processing: $AppName (File: $($ManifestFile.Name))"
    try {
        # Now, simply call 'scoop' - PowerShell should find it via the modified PATH
        Write-Output "  Running: scoop checkver '$AppName' -u"
        $ProcessOutput = scoop checkver "$AppName" -u *>&1 
        
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "  Scoop checkver for '$AppName' finished with Exit Code: $LASTEXITCODE."
        } else {
            Write-Output "  Scoop checkver for '$AppName' completed (Exit Code: 0)."
        }
        if ($ProcessOutput) {
            Write-Output "  Output from Scoop checkver for '$AppName':"
            $ProcessOutput | ForEach-Object { Write-Output "    $_" }
        }
    } catch {
        Write-Error "  An UNEXPECTED PowerShell error occurred while trying to run Scoop checkver for '$AppName': $($_.Exception.Message)"
        $GlobalSuccess = $false 
    }
    Write-Output "---------------------------" 
}

Write-Output "" 
Write-Output "===================================================================="
if ($GlobalSuccess) {
    Write-Output "Manifest version and URL update process completed its run."
} else {
    Write-Warning "Manifest version and URL update process encountered UNEXPECTED SCRIPT errors."
}
Write-Output "Script Update-ScoopVersions.ps1 (v7_final) finished."
