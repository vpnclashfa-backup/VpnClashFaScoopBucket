# Update-ScoopVersions.ps1
[CmdletBinding()]
param (
    [Parameter(Mandatory=$false)]
    [string]$BucketPath = "./bucket",

    [Parameter(Mandatory=$true)] 
    [string]$ProvidedScoopShimsPath # This path is used to derive $env:SCOOP
)

Write-Output "Script Version: v8_final_direct_call (Calls main scoop.ps1 directly)"
Write-Output "Provided BucketPath: $BucketPath"
Write-Output "Provided ScoopShimsPath from workflow: $ProvidedScoopShimsPath"

# Step 1: Determine the main Scoop installation directory ($env:SCOOP)
# The shims path is typically $SCOOP\shims. So, $SCOOP is the parent of shims path.
if (-not [string]::IsNullOrWhiteSpace($ProvidedScoopShimsPath)) {
    if (Test-Path $ProvidedScoopShimsPath -PathType Container) {
        $env:SCOOP = Split-Path $ProvidedScoopShimsPath
        Write-Output "Derived \$env:SCOOP as: $($env:SCOOP)"
    } else {
        Write-Error "CRITICAL: Provided Scoop Shims Path '$ProvidedScoopShimsPath' does NOT exist or is not a directory. Cannot derive \$env:SCOOP."
        exit 1
    }
} else {
    Write-Error "CRITICAL: No ScoopShimsPath was provided to the script. This is required to locate main Scoop script."
    exit 1
}

# Step 2: Construct the path to the main scoop.ps1 script
$MainScoopScriptPath = Join-Path $env:SCOOP "apps\scoop\current\bin\scoop.ps1"
Write-Output "Attempting to use main Scoop script at: $MainScoopScriptPath"

if (!(Test-Path $MainScoopScriptPath -PathType Leaf)) {
    Write-Error "CRITICAL FAILURE: Main Scoop script '$MainScoopScriptPath' not found. Scoop installation might be incomplete or \$env:SCOOP is incorrect."
    Write-Output "For debugging - Contents of '$($env:SCOOP)\apps\scoop\current\bin\':"
    Get-ChildItem (Join-Path $env:SCOOP "apps\scoop\current\bin\") -ErrorAction SilentlyContinue | ForEach-Object { Write-Output "  - $($_.Name)"}
    exit 1
}

Write-Output "SUCCESS: Main Scoop script found at '$MainScoopScriptPath'."
Write-Output "--------------------------------------------------------------------"

# Optional: Attempt to import Scoop module. This might help with cmdlet availability if scoop.ps1 relies on it.
$ScoopModulePath = Join-Path $env:SCOOP "apps\scoop\current\modules\scoop.psm1"
if (Test-Path $ScoopModulePath) {
    try { 
        Import-Module $ScoopModulePath -ErrorAction Stop # Use Stop to see if import itself is an issue
        Write-Output "Successfully imported Scoop module from '$ScoopModulePath'."
    } catch { 
        Write-Warning "Could not import Scoop module from '$ScoopModulePath'. Error: $($_.Exception.Message). Proceeding with direct script call."
    }
} else { 
    Write-Warning "Scoop module not found at '$ScoopModulePath' (this might be okay for direct script call)."
}
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
        # Call the main scoop.ps1 script directly using the call operator '&'
        Write-Output "  Running: & '$MainScoopScriptPath' checkver '$AppName' -u"
        $ProcessOutput = & $MainScoopScriptPath checkver "$AppName" -u *>&1 
        
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
Write-Output "Script Update-ScoopVersions.ps1 (v8_final_direct_call) finished."
