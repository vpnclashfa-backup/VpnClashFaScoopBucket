# Update-ScoopVersions.ps1
param (
    [string]$BucketPath = "./bucket"
)

Write-Output "Starting to update manifest versions and URLs in bucket: $BucketPath"
Write-Output "Attempting to ensure Scoop environment is initialized..."

# Try to explicitly import the scoop module from the default user installation path
# This path is typical for scoop installations by actions like MinoruSekine/setup-scoop
$ScoopInstallPath = Join-Path $env:USERPROFILE "scoop"
$ScoopModulePath = Join-Path $ScoopInstallPath "apps\scoop\current\modules\scoop.psm1"
$ScoopShimsPath = Join-Path $ScoopInstallPath "shims"

if (Test-Path $ScoopModulePath) {
    try {
        Import-Module $ScoopModulePath -ErrorAction Stop
        Write-Output "Scoop module imported from $ScoopModulePath"
        # Also ensure shims are in path for the current session if not already
        if ($env:PATH -notlike "*$ScoopShimsPath*") {
            $env:PATH = "$ScoopShimsPath;$env:PATH"
            Write-Output "Added $ScoopShimsPath to session PATH."
        }
    } catch {
        Write-Warning "Could not import Scoop module from $ScoopModulePath. Scoop commands might fail. Error: $($_.Exception.Message)"
    }
} else {
    Write-Warning "Scoop module not found at expected path: $ScoopModulePath. Relying on PATH."
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
        Write-Output "  Running 'scoop checkver `"$AppName`" -u'..."
        # Using scoop.exe explicitly can sometimes help in constrained environments,
        # but generally not needed if shims are in PATH correctly.
        # If issues persist, you could try: $ProcessOutput = scoop.exe checkver "$AppName" -u *>&1
        $ProcessOutput = scoop checkver "$AppName" -u *>&1  
        
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "  'scoop checkver -u' for '$AppName' may have finished with warnings or an error (Exit Code: $LASTEXITCODE)."
        } else {
            Write-Output "  'scoop checkver -u' for '$AppName' completed (or no update was found)."
        }
        if ($ProcessOutput) {
            Write-Output "  Output from scoop checkver for '$AppName':"
            $ProcessOutput | ForEach-Object { Write-Output "    $_" }
        }
    } catch {
        Write-Error "  An unexpected error occurred while running 'scoop checkver -u' for '$AppName': $($_.Exception.Message)"
        $GlobalSuccess = $false
    }
    Write-Output "---------------------------"
}

Write-Output ""
Write-Output "===================================================================="
if ($GlobalSuccess) {
    Write-Output "Manifest version and URL update process completed."
} else {
    Write-Warning "Manifest version and URL update process completed with some errors/warnings."
}