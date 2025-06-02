# Update-ScoopVersions.ps1
param (
    [string]$BucketPath = "./bucket",
    [string]$ProvidedScoopShimsPath = "" # New parameter
)

Write-Output "Starting to update manifest versions and URLs in bucket: $BucketPath"

# If a specific shims path is provided, prepend it to the current session's PATH
if (-not [string]::IsNullOrWhiteSpace($ProvidedScoopShimsPath)) {
    if (Test-Path $ProvidedScoopShimsPath) {
        Write-Output "Provided Scoop Shims Path: $ProvidedScoopShimsPath. Prepending to PATH for this script's session."
        $env:PATH = "$ProvidedScoopShimsPath;$($env:PATH)"
        Write-Output "Updated PATH for this script's session: $($env:PATH)"
    } else {
        Write-Warning "Provided Scoop Shims Path '$ProvidedScoopShimsPath' does not exist. Relying on existing PATH."
    }
} else {
    Write-Output "No explicit Scoop Shims Path provided. Relying on existing PATH or Scoop's default setup."
}

Write-Output "Attempting to ensure Scoop environment is initialized..."

# Determine Scoop root path. $env:SCOOP is usually set by Scoop itself.
$ScoopRootPath = $env:SCOOP
if (-not $ScoopRootPath -or !(Test-Path $ScoopRootPath)) {
    $ScoopRootPath = Join-Path $env:USERPROFILE "scoop"
    Write-Warning "SCOOP environment variable not found or invalid. Assuming default path: $ScoopRootPath"
} else {
    Write-Output "Using Scoop root from SCOOP environment variable: $ScoopRootPath"
}

$ScoopModulePath = Join-Path $ScoopRootPath "apps\scoop\current\modules\scoop.psm1"

# Attempt to import Scoop module (optional, as scoop.exe should work if in PATH)
if (Test-Path $ScoopModulePath) {
    try {
        Import-Module $ScoopModulePath -ErrorAction SilentlyContinue # Continue if import fails
        Write-Output "Attempted to import Scoop module from $ScoopModulePath"
    } catch {
        Write-Warning "Could not import Scoop module from $ScoopModulePath. Error: $($_.Exception.Message)"
    }
} else {
    Write-Warning "Scoop module not found at expected path: $ScoopModulePath."
}

Write-Output "--------------------------------------------------------------------"
Write-Output "Verifying scoop.exe command availability..."
$ScoopExeCommand = Get-Command scoop.exe -ErrorAction SilentlyContinue
if ($ScoopExeCommand) {
    Write-Output "scoop.exe found by Get-Command at: $($ScoopExeCommand.Source)"
} else {
    Write-Error "scoop.exe NOT FOUND by Get-Command in this script's context. Cannot proceed with checkver."
    # Try to list directories in PATH for debugging
    Write-Output "Current PATH directories:"
    $env:PATH -split ';' | ForEach-Object { Write-Output "  - $_" }
    exit 1
}
Write-Output "--------------------------------------------------------------------"


$ManifestFiles = Get-ChildItem -Path $BucketPath -Filter "*.json" -File -ErrorAction SilentlyContinue

if (-not $ManifestFiles) {
    Write-Warning "No manifest files (.json) found in '$BucketPath'."
    exit 0 # Exit gracefully if no files to process
}

$GlobalSuccess = $true 

foreach ($ManifestFile in $ManifestFiles) {
    $AppName = $ManifestFile.BaseName
    Write-Output ""
    Write-Output "Processing: $AppName (File: $($ManifestFile.Name))"

    try {
        Write-Output "  Running 'scoop.exe checkver `"$AppName`" -u'..."
        $ProcessOutput = scoop.exe checkver "$AppName" -u *>&1
        
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "  'scoop.exe checkver -u' for '$AppName' likely finished with warnings (e.g., no update found) or an error (Exit Code: $LASTEXITCODE)."
        } else {
            Write-Output "  'scoop.exe checkver -u' for '$AppName' completed successfully (or an update was applied)."
        }

        if ($ProcessOutput) {
            Write-Output "  Output from scoop.exe checkver for '$AppName':"
            $ProcessOutput | ForEach-Object { Write-Output "    $_" }
        }

    } catch {
        Write-Error "  An UNEXPECTED error occurred while running 'scoop.exe checkver -u' for '$AppName': $($_.Exception.Message)"
        $GlobalSuccess = $false
    }
    Write-Output "---------------------------"
}

Write-Output ""
Write-Output "===================================================================="
if ($GlobalSuccess) {
    Write-Output "Manifest version and URL update process completed its run."
    Write-Output "Review individual app logs for specific checkver outcomes."
} else {
    Write-Warning "Manifest version and URL update process completed with some UNEXPECTED SCRIPT errors."
}
