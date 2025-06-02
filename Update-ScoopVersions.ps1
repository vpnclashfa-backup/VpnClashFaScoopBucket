# Update-ScoopVersions.ps1
[CmdletBinding()]
param (
    [Parameter(Mandatory=$false)]
    [string]$BucketPath = "./bucket",

    [Parameter(Mandatory=$true)]
    [string]$ProvidedScoopShimsPath # Used to derive $env:SCOOP
)

Write-Output "Script Version: v9_module_focus"
Write-Output "Provided BucketPath: $BucketPath"
Write-Output "Provided ScoopShimsPath from workflow: $ProvidedScoopShimsPath"

# Step 1: Ensure $env:SCOOP is set correctly from the shims path
if (-not [string]::IsNullOrWhiteSpace($ProvidedScoopShimsPath)) {
    if (Test-Path $ProvidedScoopShimsPath -PathType Container) {
        $env:SCOOP = Split-Path $ProvidedScoopShimsPath # $SCOOP is parent of shims
        Write-Output "Derived \$env:SCOOP as: $($env:SCOOP)"
    } else {
        Write-Error "CRITICAL: Provided Scoop Shims Path '$ProvidedScoopShimsPath' does NOT exist or is not a directory. Cannot derive \$env:SCOOP."
        exit 1
    }
} else {
    Write-Error "CRITICAL: No ScoopShimsPath was provided. This is required to locate the Scoop module."
    exit 1
}

# Step 2: Attempt to forcefully find and load the Scoop module
$ScoopModulePath = Join-Path $env:SCOOP "apps\scoop\current\modules\scoop.psm1"
$ScoopModuleDir = Split-Path $ScoopModulePath
Write-Output "Attempting to ensure Scoop module is available from: $ScoopModulePath"

if (Test-Path $ScoopModulePath -PathType Leaf) {
    Write-Output "Scoop module file FOUND at '$ScoopModulePath'."
    
    # Temporarily add the module's directory to PSModulePath to aid discovery, though full path import should work.
    $OriginalPSModulePath = $env:PSModulePath
    $env:PSModulePath = "$ScoopModuleDir;$($env:PSModulePath)"
    Write-Output "Temporarily prepended '$ScoopModuleDir' to \$env:PSModulePath for module discovery."
    
    try {
        Write-Output "Attempting to import Scoop module with -Force and -Verbose..."
        Import-Module $ScoopModulePath -Force -Verbose 
        Write-Output "SUCCESS: Scoop module should now be imported."
        
        # Verify if 'scoop' command (as a function/alias from module) is now available
        $ScoopCommandInfo = Get-Command scoop -CommandType Function,Alias,Cmdlet -ErrorAction SilentlyContinue
        if ($ScoopCommandInfo) {
            Write-Output "'scoop' command (from module) is available. Type: $($ScoopCommandInfo.CommandType), Source: $($ScoopCommandInfo.Definition)"
        } else {
            Write-Warning "'scoop' command (as function/alias/cmdlet) still not found after module import. This is unexpected. Will rely on PATH for scoop.ps1/scoop.cmd if necessary."
        }
    } catch {
        Write-Error "CRITICAL FAILURE: Could not import Scoop module from '$ScoopModulePath' even though the file exists. Error: $($_.Exception.Message)"
        $env:PSModulePath = $OriginalPSModulePath # Restore original module path
        exit 1
    }
    $env:PSModulePath = $OriginalPSModulePath # Restore original module path in all cases after attempt
} else {
    Write-Error "CRITICAL FAILURE: Scoop module file '$ScoopModulePath' NOT FOUND. Scoop installation is likely incomplete or \$env:SCOOP is incorrect."
    Write-Output "For debugging - Contents of '$($env:SCOOP)\apps\scoop\current\modules\':"
    Get-ChildItem (Join-Path $env:SCOOP "apps\scoop\current\modules\") -ErrorAction SilentlyContinue | ForEach-Object { Write-Output "  - $($_.Name)"}
    exit 1
}

Write-Output "--------------------------------------------------------------------"
# At this point, the Scoop module should be loaded. 
# The 'scoop' command should ideally refer to a function/cmdlet from this module.

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
        # Call 'scoop' directly. PowerShell should resolve this to the function/cmdlet from the imported module.
        Write-Output "  Running: scoop checkver '$AppName' -u (expecting module's function/cmdlet)"
        $ProcessOutput = scoop checkver "$AppName" -u *>&1 

        if ($LASTEXITCODE -ne 0) { # $LASTEXITCODE might not be relevant if 'scoop' is a function; errors would be exceptions
            Write-Warning "  Scoop checkver for '$AppName' finished. Exit Code (if applicable): $LASTEXITCODE."
        } else {
            Write-Output "  Scoop checkver for '$AppName' completed (Exit Code (if applicable): 0)."
        }
        if ($ProcessOutput) {
            Write-Output "  Output from Scoop checkver for '$AppName':"
            $ProcessOutput | ForEach-Object { Write-Output "    $_" }
        }
    } catch { # Catch exceptions if 'scoop' or 'checkver' is a function that throws
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
}
Write-Output "Script Update-ScoopVersions.ps1 (v9_module_focus) finished."
