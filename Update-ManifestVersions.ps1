# Update-ManifestVersions.ps1
# This script updates the version and URL of all Scoop manifests in the specified bucket directory.

param (
    [string]$BucketPath = "./bucket" # Path to the directory containing the .json manifest files
)

Write-Host "Starting to update manifest versions and URLs in bucket: $BucketPath"
Write-Host "--------------------------------------------------------------------"

$ManifestFiles = Get-ChildItem -Path $BucketPath -Filter "*.json" -File -ErrorAction SilentlyContinue

if (-not $ManifestFiles) {
    Write-Warning "No manifest files (.json) found in '$BucketPath'."
    exit 0 # Exit successfully as there's nothing to do
}

$GlobalSuccess = $true

foreach ($ManifestFile in $ManifestFiles) {
    $AppName = $ManifestFile.BaseName
    Write-Host ""
    Write-Host "Processing: $AppName (File: $($ManifestFile.Name))"

    try {
        Write-Host "  Running 'scoop checkver `"$AppName`" -u'..."
        # Execute scoop checkver. The -u flag attempts to update the manifest file directly.
        # We capture all output streams.
        $ProcessOutput = scoop checkver "$AppName" -u *>&1 
        
        # Check the exit code of the last command
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "  'scoop checkver -u' for '$AppName' finished with exit code $LASTEXITCODE."
            if ($ProcessOutput) {
                Write-Warning "  Output from scoop checkver:"
                $ProcessOutput | ForEach-Object { Write-Warning "    $_" }
            }
            # Even if checkver warns or fails for one app, continue with others
            # but mark overall success as false if it's a real error (e.g., command not found)
            # For now, we'll just log it. The Python script will handle hash updates based on current content.
            # If 'scoop' itself is not found, this will be a problem for all.
        } else {
            Write-Host "  'scoop checkver -u' for '$AppName' completed."
            if ($ProcessOutput) {
                Write-Host "  Output from scoop checkver:"
                $ProcessOutput | ForEach-Object { Write-Host "    $_" }
            }
        }
    } catch {
        Write-Error "  An unexpected error occurred while running 'scoop checkver -u' for '$AppName': $($_.Exception.Message)"
        $GlobalSuccess = $false
    }
    Write-Host "---------------------------"
}

Write-Host ""
Write-Host "===================================================================="
if ($GlobalSuccess) {
    Write-Host "Manifest version and URL update process completed."
} else {
    Write-Warning "Manifest version and URL update process completed with some errors/warnings."
}
# This script doesn't directly fail the workflow for checkver errors for individual apps,
# as the Python script can still attempt to update hashes.
# However, if 'scoop' command itself fails, that's a setup issue for the Action.
