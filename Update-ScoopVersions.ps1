# Update-ScoopVersions.ps1
[CmdletBinding()]
param (
    [Parameter(Mandatory=$false)]
    [string]$BucketPath = "./bucket",

    [Parameter(Mandatory=$true)] # This path is used to derive $env:SCOOP
    [string]$ProvidedScoopShimsPath 
)

Write-Output "Script Version: v10_module_critical"
Write-Output "Provided BucketPath: $BucketPath"
Write-Output "Provided ScoopShimsPath from workflow: $ProvidedScoopShimsPath"

# Step 1: Determine $env:SCOOP from $ProvidedScoopShimsPath
if (-not [string]::IsNullOrWhiteSpace($ProvidedScoopShimsPath)) {
    if (Test-Path $ProvidedScoopShimsPath -PathType Container) {
        $env:SCOOP = Split-Path $ProvidedScoopShimsPath # $SCOOP is the parent directory of 'shims'
        Write-Output "Derived \$env:SCOOP as: $($env:SCOOP)"
        # Also ensure shims path is in the current script's PATH for good measure, though module import is key
        if ($env:PATH -notlike "*$ProvidedScoopShimsPath*") {
            $env:PATH = "$ProvidedScoopShimsPath;$($env:PATH)"
            Write-Output "Prepended '$ProvidedScoopShimsPath' to this script's session PATH."
        }
    } else {
        Write-Error "CRITICAL: Provided Scoop Shims Path '$ProvidedScoopShimsPath' does NOT exist or is not a directory. Cannot derive \$env:SCOOP."
        exit 1
    }
} else {
    Write-Error "CRITICAL: No ScoopShimsPath was provided. This is required to locate the Scoop module."
    exit 1
}

# Step 2: CRITICAL - Find and import the Scoop module (scoop.psm1)
$ScoopModulePath = Join-Path $env:SCOOP "apps\scoop\current\modules\scoop.psm1"
$ScoopModuleDir = Split-Path $ScoopModulePath
Write-Output "Attempting to find and import Scoop module from: '$ScoopModulePath'"

if (Test-Path $ScoopModulePath -PathType Leaf) {
    Write-Output "Scoop module file FOUND at '$ScoopModulePath'."
    
    # Add the module's directory to PSModulePath to help PowerShell find it, then import by full path.
    $OriginalPSModulePath = $env:PSModulePath
    $env:PSModulePath = "$ScoopModuleDir;$($env:PSModulePath)"
    Write-Output "Temporarily prepended '$ScoopModuleDir' to \$env:PSModulePath."
    
    try {
        Write-Output "Attempting to import Scoop module with -Force and -Verbose..."
        Import-Module $ScoopModulePath -Force -Verbose 
        Write-Output "SUCCESS: Scoop module imported (or re-imported)."
        
        # Verify if 'scoop' command (as a function/alias from module) is now available
        $ScoopCommandInfo = Get-Command scoop -CommandType Function,Alias,Cmdlet -ErrorAction SilentlyContinue
        if ($ScoopCommandInfo) {
            Write-Output "'scoop' command (from module) is now available. Type: $($ScoopCommandInfo.CommandType), Definition/Source: $($ScoopCommandInfo.Definition)"
        } else {
            # This would be very strange if the module imported successfully but didn't define 'scoop'
            Write-Error "CRITICAL UNEXPECTED: 'scoop' command (as function/alias/cmdlet) NOT found after successful module import. Scoop installation might be corrupted."
            exit 1
        }
    } catch {
        Write-Error "CRITICAL FAILURE: Could not import Scoop module from '$ScoopModulePath' even though the file exists. Error: $($_.Exception.Message)"
        $env:PSModulePath = $OriginalPSModulePath # Restore original module path
        exit 1 # Fail the script if module import fails
    }
    $env:PSModulePath = $OriginalPSModulePath # Restore original module path
} else {
    Write-Error "CRITICAL FAILURE: Scoop module file '$ScoopModulePath' NOT FOUND. The 'scoop update scoop' command in the workflow might not have fully provisioned the 'scoop' app."
    Write-Output "For debugging - Contents of '$($env:SCOOP)\apps\scoop\current\modules\' (if it exists):"
    Get-ChildItem (Join-Path $env:SCOOP "apps\scoop\current\modules") -ErrorAction SilentlyContinue | ForEach-Object { Write-Output "  - $($_.Name)"}
    exit 1 # Fail the script if module file is not found
}

Write-Output "--------------------------------------------------------------------"
# At this point, the Scoop module MUST be loaded. 
# The 'scoop' command should refer to a function/cmdlet from this module.

$ManifestFiles = Get-ChildItem -Path $BucketPath -Filter "*.json" -File -ErrorAction SilentlyContinue
if (-not $ManifestFiles) {
    Write-Warning "No manifest files (.json) found in '$BucketPath'."
    exit 0 # Not an error, just no work to do for this part
}

$GlobalSuccess = $true # Tracks success of checkver operations
foreach ($ManifestFileItem in $ManifestFiles) {
    $AppName = $ManifestFileItem.BaseName
    Write-Output ""
    Write-Output "Processing: $AppName (File: $($ManifestFileItem.Name))"
    try {
        # Call 'scoop' directly. PowerShell should resolve this to the function/cmdlet from the imported module.
        Write-Output "  Running: scoop checkver '$AppName' -u (using imported module's command)"
        $ProcessOutput = scoop checkver "$AppName" -u *>&1 

        # $LASTEXITCODE is for external commands. For PowerShell functions/cmdlets, errors are typically exceptions.
        # However, 'scoop checkver' might still internally call executables or set $LASTEXITCODE.
        if ($LASTEXITCODE -ne 0) { 
            Write-Warning "  Scoop checkver for '$AppName' finished. Exit Code (if applicable): $LASTEXITCODE."
        } else {
            Write-Output "  Scoop checkver for '$AppName' completed (Exit Code (if applicable): 0)."
        }
        if ($ProcessOutput) {
            Write-Output "  Output from Scoop checkver for '$AppName':"
            $ProcessOutput | ForEach-Object { Write-Output "    $_" }
        }
    } catch { # Catch exceptions if 'scoop' or 'checkver' (as a function) throws an error
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
    Write-Warning "Manifest version and URL update process encountered UNEXPECTED SCRIPT errors/exceptions."
    # exit 1 # Optionally fail the entire script if any checkver had an issue
}
Write-Output "Script Update-ScoopVersions.ps1 (v10_module_critical) finished."
