# Update-ScoopVersions.ps1
[CmdletBinding()]
param (
    [Parameter(Mandatory=$true)]
    [string]$BucketPath # Path to the bucket directory, e.g., "./bucket"
)

Write-Output "Script Version: v13_scoop_source_env"
Write-Output "Provided BucketPath: $BucketPath"

# Step 1: Validate $env:SCOOP_HOME (must be set by the GitHub Actions workflow)
if ([string]::IsNullOrWhiteSpace($env:SCOOP_HOME) -or !(Test-Path $env:SCOOP_HOME -PathType Container)) {
    Write-Error "CRITICAL: \$env:SCOOP_HOME is not set by the workflow or points to an invalid directory."
    Write-Error "This script expects \$env:SCOOP_HOME to be the root of a Scoop source code checkout."
    Write-Error "Current \$env:SCOOP_HOME value: '$($env:SCOOP_HOME)'"
    exit 1
}
Write-Output "\$env:SCOOP_HOME is set to: $($env:SCOOP_HOME)"

# Step 2: CRITICAL - Find and import the Scoop module (scoop.psm1) from $env:SCOOP_HOME\modules
$ScoopModulePath = Join-Path $env:SCOOP_HOME "modules\scoop.psm1"
$ScoopModuleDir = Split-Path $ScoopModulePath # Should be $env:SCOOP_HOME\modules
Write-Output "Attempting to find and import Scoop module from: '$ScoopModulePath'"

if (Test-Path $ScoopModulePath -PathType Leaf) {
    Write-Output "Scoop module file FOUND at '$ScoopModulePath'."
    
    $OriginalPSModulePath = $env:PSModulePath
    # Add the module's parent directory ($env:SCOOP_HOME\modules) to PSModulePath
    # This helps PowerShell resolve any dependencies the module itself might have from its own directory.
    if ($env:PSModulePath -notlike "*$ScoopModuleDir*") {
        $env:PSModulePath = "$ScoopModuleDir;$($env:PSModulePath)"
        Write-Output "Temporarily prepended '$ScoopModuleDir' to \$env:PSModulePath for module discovery."
    }
    
    try {
        Write-Output "Attempting to import Scoop module '$ScoopModulePath' with -Force and -Verbose..."
        Import-Module $ScoopModulePath -Force -Verbose 
        Write-Output "SUCCESS: Scoop module imported (or re-imported)."
        
        # Verify if 'scoop' command (as a function/alias from module) is now available
        $ScoopCommandInfo = Get-Command scoop -CommandType Function,Alias,Cmdlet -ErrorAction SilentlyContinue
        if ($ScoopCommandInfo) {
            Write-Output "'scoop' command (from module) is now available. Type: $($ScoopCommandInfo.CommandType), Definition/Source: $($ScoopCommandInfo.Definition)"
        } else {
            Write-Error "CRITICAL UNEXPECTED: 'scoop' command (as function/alias/cmdlet) NOT found after successful module import. This should not happen if the module loaded correctly."
            exit 1
        }
    } catch {
        Write-Error "CRITICAL FAILURE: Could not import Scoop module from '$ScoopModulePath'. Error: $($_.Exception.Message)"
        $env:PSModulePath = $OriginalPSModulePath # Restore original module path
        exit 1 
    }
    # Consider restoring $OriginalPSModulePath if it's confirmed not to break anything,
    # but for the duration of this script, having the module's dir in path might be safer.
    # $env:PSModulePath = $OriginalPSModulePath 
} else {
    Write-Error "CRITICAL FAILURE: Scoop module file '$ScoopModulePath' NOT FOUND in \$env:SCOOP_HOME ('$($env:SCOOP_HOME)\modules')."
    Write-Output "For debugging - Contents of '$($env:SCOOP_HOME)\modules\' (if it exists):"
    Get-ChildItem (Join-Path $env:SCOOP_HOME "modules") -ErrorAction SilentlyContinue | ForEach-Object { Write-Output "  - $($_.Name)"}
    exit 1 
}

Write-Output "--------------------------------------------------------------------"
# At this point, the Scoop module MUST be loaded.

$ManifestFiles = Get-ChildItem -Path $BucketPath -Filter "*.json" -File -ErrorAction SilentlyContinue
if (-not $ManifestFiles) {
    Write-Warning "No manifest files (.json) found in '$BucketPath'."
    exit 0 # Not an error, just no work to do for this part
}

$GlobalSuccess = $true 
foreach ($ManifestFileItem in $ManifestFiles) {
    $AppName = $ManifestFileItem.BaseName
    Write-Output ""
    Write-Output "Processing: $AppName (File: $($ManifestFileItem.Name))"
    try {
        Write-Output "  Running: scoop checkver '$AppName' -u (using imported module's command)"
        # $LASTEXITCODE is less relevant for module functions; errors are exceptions.
        # Scoop's 'checkver' function might still internally call executables or set $LASTEXITCODE.
        $ProcessOutput = scoop checkver "$AppName" -u *>&1 

        $OutputString = $ProcessOutput -join "`n" # Join all output lines for easier matching
        
        # Check for known failure patterns in the output
        if ($OutputString -match "isn't a scoop command") {
            Write-Error "  Scoop reported 'checkver' is not a command for '$AppName'. This indicates a problem with the Scoop module or command dispatch."
            $GlobalSuccess = $false # This is a failure of the checkver command itself
        } elseif ($LASTEXITCODE -ne 0) { 
            Write-Warning "  Scoop checkver for '$AppName' finished. Exit Code (if applicable): $LASTEXITCODE."
            # Non-zero exit code doesn't always mean failure of the whole process, could be app-specific
        } else {
            Write-Output "  Scoop checkver for '$AppName' completed (Exit Code (if applicable): 0)."
        }

        if ($ProcessOutput) {
            Write-Output "  Output from Scoop checkver for '$AppName':"
            $ProcessOutput | ForEach-Object { Write-Output "    $_" }
        }
    } catch { # Catch PowerShell exceptions (e.g., if 'scoop' function itself throws)
        Write-Error "  An UNEXPECTED PowerShell error/exception occurred while running Scoop checkver for '$AppName': $($_.Exception.Message)"
        $GlobalSuccess = $false
    }
    Write-Output "---------------------------"
}

Write-Output ""
Write-Output "===================================================================="
if ($GlobalSuccess) {
    Write-Output "Manifest version and URL update process completed its run."
} else {
    Write-Warning "Manifest version and URL update process encountered checkver failures or UNEXPECTED SCRIPT errors/exceptions."
    # exit 1 # Optionally fail the entire script if any checkver had a critical issue
}
Write-Output "Script Update-ScoopVersions.ps1 (v13_scoop_source_env) finished."
