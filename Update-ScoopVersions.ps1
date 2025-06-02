# Update-ScoopVersions.ps1
[CmdletBinding()] # Enables support for common parameters like -Verbose, -Debug, -ErrorAction
param (
    [Parameter(Mandatory=$false)] # Made BucketPath non-mandatory, will default
    [string]$BucketPath = "./bucket",

    [Parameter(Mandatory=$false)] # Shims path is optional but recommended for CI
    [string]$ProvidedScoopShimsPath = "" 
)

Write-Verbose "Starting script: Update-ScoopVersions.ps1"
Write-Output "Starting to update manifest versions and URLs in bucket: $BucketPath"

$ScoopExecutablePath = $null # Initialize to null

# Priority 1: Use explicitly provided shims path to construct scoop.exe path
if (-not [string]::IsNullOrWhiteSpace($ProvidedScoopShimsPath)) {
    Write-Verbose "ProvidedScoopShimsPath is: '$ProvidedScoopShimsPath'"
    if (Test-Path $ProvidedScoopShimsPath -PathType Container) { # Check if it's a directory
        $PotentialScoopExe = Join-Path $ProvidedScoopShimsPath "scoop.exe"
        if (Test-Path $PotentialScoopExe -PathType Leaf) { # Check if scoop.exe exists and is a file
            $ScoopExecutablePath = $PotentialScoopExe
            Write-Output "Using explicit Scoop executable path: $ScoopExecutablePath"
        } else {
            Write-Warning "scoop.exe not found at the end of provided shims path: '$PotentialScoopExe'. Will attempt Get-Command."
        }
    } else {
        Write-Warning "Provided Scoop Shims Path '$ProvidedScoopShimsPath' does not exist or is not a directory. Will attempt Get-Command."
    }
} else {
    Write-Verbose "No explicit Scoop Shims Path provided via parameter. Will attempt Get-Command."
}

# Priority 2: Fallback to Get-Command if explicit path wasn't resolved
if ([string]::IsNullOrWhiteSpace($ScoopExecutablePath)) {
    Write-Output "Attempting to find scoop.exe using Get-Command..."
    $ScoopCmdInfo = Get-Command scoop.exe -ErrorAction SilentlyContinue
    if ($ScoopCmdInfo) {
        $ScoopExecutablePath = $ScoopCmdInfo.Source
        Write-Output "Found scoop.exe via Get-Command at: $ScoopExecutablePath"
    } else {
        Write-Error "CRITICAL: scoop.exe could not be found via explicit path or Get-Command. Cannot proceed."
        Write-Output "For debugging - Current PATH directories:"
        $env:PATH -split ';' | ForEach-Object { Write-Output "  - $_" }
        exit 1 # Exit with an error code if scoop.exe is not found
    }
}

Write-Output "--------------------------------------------------------------------"
# The following SCOOP env var and module import are less critical if we have the direct exe path,
# but kept for completeness or if scoop internals rely on them.
Write-Verbose "Attempting to ensure Scoop environment variables and modules are sensible..."
$env:SCOOP = Split-Path (Split-Path $ScoopExecutablePath) # Set SCOOP to parent of shims
Write-Output "Ensured \$env:SCOOP is set to: $($env:SCOOP)"

$ScoopModulePath = Join-Path $env:SCOOP "apps\scoop\current\modules\scoop.psm1"
if (Test-Path $ScoopModulePath) {
    try {
        Import-Module $ScoopModulePath -ErrorAction SilentlyContinue
        Write-Verbose "Attempted to import Scoop module from $ScoopModulePath"
    } catch { Write-Warning "Could not import Scoop module from '$ScoopModulePath'. Error: $($_.Exception.Message)" }
} else { Write-Verbose "Scoop module not found at '$ScoopModulePath' (this is often okay)." }
Write-Output "--------------------------------------------------------------------"


$ManifestFiles = Get-ChildItem -Path $BucketPath -Filter "*.json" -File -ErrorAction SilentlyContinue

if (-not $ManifestFiles) {
    Write-Warning "No manifest files (.json) found in '$BucketPath'."
    exit 0 # Exit gracefully if no files to process, this is not an error.
}

$GlobalSuccess = $true # Assume overall success unless an unexpected script error occurs

foreach ($ManifestFile in $ManifestFiles) {
    $AppName = $ManifestFile.BaseName
    Write-Output "" # Newline for readability
    Write-Output "Processing: $AppName (File: $($ManifestFile.Name))"

    try {
        Write-Output "  Running: & '$ScoopExecutablePath' checkver '$AppName' -u"
        # Use the call operator '&' to execute the command when path is in a variable
        # Capture all streams by redirecting them to success stream (1) then to variable
        $ProcessOutput = & $ScoopExecutablePath checkver "$AppName" -u *>&1 
        
        if ($LASTEXITCODE -ne 0) {
            # Non-zero exit code from scoop checkver is not necessarily a script failure.
            # It can mean "no update found", "check failed for specific app", etc.
            Write-Warning "  Scoop checkver for '$AppName' finished with Exit Code: $LASTEXITCODE. This may indicate no update or an app-specific issue."
        } else {
            Write-Output "  Scoop checkver for '$AppName' completed (Exit Code: 0 - likely success or update applied)."
        }

        if ($ProcessOutput) {
            Write-Output "  Output from Scoop checkver for '$AppName':"
            $ProcessOutput | ForEach-Object { Write-Output "    $_" } # Indent output for readability
        }

    } catch {
        # This catch block is for unexpected PowerShell script errors, not for scoop command errors.
        Write-Error "  An UNEXPECTED PowerShell error occurred while trying to run Scoop checkver for '$AppName': $($_.Exception.Message)"
        $GlobalSuccess = $false # Mark global success as false for unexpected script errors
    }
    Write-Output "---------------------------" # Separator for each app
}

Write-Output "" # Newline for readability
Write-Output "===================================================================="
if ($GlobalSuccess) {
    Write-Output "Manifest version and URL update process completed its run."
    Write-Output "Review individual app logs above for specific 'scoop checkver' outcomes."
} else {
    Write-Warning "Manifest version and URL update process encountered UNEXPECTED SCRIPT errors."
    # Consider exiting with a non-zero code if $GlobalSuccess is false to fail the GitHub Actions step
    # exit 1 
}
Write-Output "Script finished."
