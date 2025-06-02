# Update-ScoopVersions.ps1
[CmdletBinding()]
param (
    [Parameter(Mandatory=$false)]
    [string]$BucketPath = "./bucket",

    [Parameter(Mandatory=$true)] # Make this mandatory to ensure it's always passed from workflow
    [string]$ProvidedScoopShimsPath = "" 
)

Write-Verbose "Starting script: Update-ScoopVersions.ps1"
Write-Output "Script Version: v6_full" # Add a version marker to the script itself for easy identification in logs
Write-Output "Provided BucketPath: $BucketPath"
Write-Output "Provided ScoopShimsPath: $ProvidedScoopShimsPath"

$ScoopExecutablePath = $null 

# Step 1: Validate the provided shims path and construct the explicit path to scoop.exe
if (-not [string]::IsNullOrWhiteSpace($ProvidedScoopShimsPath)) {
    Write-Output "Validating provided shims path: '$ProvidedScoopShimsPath'"
    if (Test-Path $ProvidedScoopShimsPath -PathType Container) {
        Write-Output "Provided shims path '$ProvidedScoopShimsPath' exists and is a directory."
        $PotentialScoopExe = Join-Path $ProvidedScoopShimsPath "scoop.exe"
        Write-Output "Testing for scoop.exe at: '$PotentialScoopExe'"
        if (Test-Path $PotentialScoopExe -PathType Leaf) {
            $ScoopExecutablePath = $PotentialScoopExe
            Write-Output "SUCCESS: scoop.exe found at explicit path: $ScoopExecutablePath"
        } else {
            Write-Warning "scoop.exe NOT FOUND as a file at '$PotentialScoopExe'."
            Write-Output "Listing contents of '$ProvidedScoopShimsPath' for debugging:"
            Get-ChildItem -Path $ProvidedScoopShimsPath | ForEach-Object { Write-Output "  - $($_.Name) (Type: $($_.GetType().Name))" }
        }
    } else {
        Write-Warning "Provided Scoop Shims Path '$ProvidedScoopShimsPath' does NOT exist or is not a directory."
    }
} else {
    # This case should not happen if workflow passes it correctly and param is mandatory
    Write-Error "CRITICAL: No ScoopShimsPath was provided to the script. This is required."
    exit 1
}

# Step 2: If explicit path to scoop.exe was not resolved, try Get-Command as a last resort (and likely fail based on history)
if ([string]::IsNullOrWhiteSpace($ScoopExecutablePath)) {
    Write-Warning "Explicit path to scoop.exe could not be resolved. Attempting Get-Command as a fallback..."
    $ScoopCmdInfo = Get-Command scoop.exe -ErrorAction SilentlyContinue
    if ($ScoopCmdInfo) {
        $ScoopExecutablePath = $ScoopCmdInfo.Source
        Write-Output "Fallback SUCCESS: Found scoop.exe via Get-Command at: $ScoopExecutablePath"
    } else {
        Write-Error "CRITICAL FAILURE: scoop.exe could not be found via explicit path construction OR Get-Command. Cannot proceed."
        Write-Output "For debugging - Current PATH directories in this script's scope:"
        $env:PATH -split ';' | ForEach-Object { Write-Output "  - $_" }
        exit 1 
    }
}

Write-Output "--------------------------------------------------------------------"
Write-Verbose "Ensuring \$env:SCOOP is sensible based on determined shims path..."
# Set SCOOP env var to the parent directory of shims (e.g., C:\Users\runneradmin\scoop)
$env:SCOOP = Split-Path $ProvidedScoopShimsPath 
Write-Output "Set \$env:SCOOP to: $($env:SCOOP)"

# Optional: Attempt to import Scoop module. Not strictly necessary if calling scoop.exe directly.
$ScoopModulePath = Join-Path $env:SCOOP "apps\scoop\current\modules\scoop.psm1"
if (Test-Path $ScoopModulePath) {
    try {
        Import-Module $ScoopModulePath -ErrorAction SilentlyContinue
        Write-Verbose "Attempted to import Scoop module from $ScoopModulePath"
    } catch { Write-Warning "Could not import Scoop module from '$ScoopModulePath'. Error: $($_.Exception.Message)" }
} else { Write-Verbose "Scoop module not found at '$ScoopModulePath'." }
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
        Write-Output "  Running: & '$ScoopExecutablePath' checkver '$AppName' -u"
        $ProcessOutput = & $ScoopExecutablePath checkver "$AppName" -u *>&1 
        
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
    # exit 1 # Optionally fail the step if there were script errors
}
Write-Output "Script Update-ScoopVersions.ps1 (v6_full) finished."
