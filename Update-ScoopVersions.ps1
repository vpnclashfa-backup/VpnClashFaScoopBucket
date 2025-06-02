# Update-ScoopVersions.ps1
param (
    [string]$BucketPath = "./bucket"
)

Write-Output "Starting to update manifest versions and URLs in bucket: $BucketPath"
Write-Output "Attempting to ensure Scoop environment is initialized..."

# Determine Scoop root path. $env:SCOOP is usually set by Scoop itself.
# If not, fall back to the default user profile path.
$ScoopRootPath = $env:SCOOP
if (-not $ScoopRootPath -or !(Test-Path $ScoopRootPath)) {
    $ScoopRootPath = Join-Path $env:USERPROFILE "scoop"
    Write-Warning "SCOOP environment variable not found or invalid. Assuming default path: $ScoopRootPath"
} else {
    Write-Output "Using Scoop root from SCOOP environment variable: $ScoopRootPath"
}

$ScoopModulePath = Join-Path $ScoopRootPath "apps\scoop\current\modules\scoop.psm1"
$ScoopShimsPath = Join-Path $ScoopRootPath "shims"

if (Test-Path $ScoopModulePath) {
    try {
        Import-Module $ScoopModulePath -ErrorAction Stop
        Write-Output "Scoop module imported from $ScoopModulePath"
        # Ensure shims are in path for the current session if not already (belt-and-suspenders)
        if ($env:PATH -notlike "*$ScoopShimsPath*") {
            $env:PATH = "$ScoopShimsPath;$env:PATH"
            Write-Output "Added $ScoopShimsPath to session PATH."
        }
    } catch {
        Write-Warning "Could not import Scoop module from $ScoopModulePath. Scoop commands might still work if scoop.exe is in PATH. Error: $($_.Exception.Message)"
    }
} else {
    Write-Warning "Scoop module not found at expected path: $ScoopModulePath. Relying on scoop.exe in PATH."
}

Write-Output "--------------------------------------------------------------------"
Write-Output "Verifying scoop.exe command availability..."
$ScoopExeCommand = Get-Command scoop.exe -ErrorAction SilentlyContinue
if ($ScoopExeCommand) {
    Write-Output "scoop.exe found at: $($ScoopExeCommand.Source)"
} else {
    Write-Error "scoop.exe not found in PATH. Cannot proceed with checkver."
    exit 1
}
Write-Output "--------------------------------------------------------------------"


$ManifestFiles = Get-ChildItem -Path $BucketPath -Filter "*.json" -File -ErrorAction SilentlyContinue

if (-not $ManifestFiles) {
    Write-Warning "No manifest files (.json) found in '$BucketPath'."
    exit 0 # Exit gracefully if no files to process
}

$GlobalSuccess = $true # Assume success unless an unexpected error occurs

foreach ($ManifestFile in $ManifestFiles) {
    $AppName = $ManifestFile.BaseName
    Write-Output ""
    Write-Output "Processing: $AppName (File: $($ManifestFile.Name))"

    try {
        Write-Output "  Running 'scoop.exe checkver `"$AppName`" -u'..."
        # Explicitly call scoop.exe
        $ProcessOutput = scoop.exe checkver "$AppName" -u *>&1
        
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "  'scoop.exe checkver -u' for '$AppName' likely finished with warnings (e.g., no update found) or an error (Exit Code: $LASTEXITCODE)."
            # Note: 'scoop checkver' can exit with non-zero for legitimate reasons like app already up-to-date.
            # We don't set $GlobalSuccess = $false here unless it's an unexpected script error.
        } else {
            Write-Output "  'scoop.exe checkver -u' for '$AppName' completed successfully (or an update was applied)."
        }

        if ($ProcessOutput) {
            Write-Output "  Output from scoop.exe checkver for '$AppName':"
            $ProcessOutput | ForEach-Object { Write-Output "    $_" }
        }

    } catch {
        Write-Error "  An UNEXPECTED error occurred while running 'scoop.exe checkver -u' for '$AppName': $($_.Exception.Message)"
        $GlobalSuccess = $false # This is for true script errors, not scoop command exit codes
    }
    Write-Output "---------------------------"
}

Write-Output ""
Write-Output "===================================================================="
if ($GlobalSuccess) {
    Write-Output "Manifest version and URL update process completed its run."
    Write-Output "Review individual app logs for specific checkver outcomes (updates, warnings, errors)."
} else {
    Write-Warning "Manifest version and URL update process completed with some UNEXPECTED SCRIPT errors."
}
# The workflow's continue-on-error handles whether the job proceeds.
# This script doesn't need to force an exit code unless a catastrophic failure occurs early.
