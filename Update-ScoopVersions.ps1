# Update-ScoopVersions.ps1
# This script updates the version and URL of all Scoop manifests in the specified bucket directory
# using 'scoop checkver -u'. It should be run by the GitHub Action in a PowerShell environment
# where Scoop is properly initialized.

param (
    [string]$BucketPath = "./bucket" # Path to the directory containing the .json manifest files
)

Write-Output "Starting to update manifest versions and URLs in bucket: $BucketPath"
Write-Output "--------------------------------------------------------------------"

$ManifestFiles = Get-ChildItem -Path $BucketPath -Filter "*.json" -File -ErrorAction SilentlyContinue

if (-not $ManifestFiles) {
    Write-Warning "No manifest files (.json) found in '$BucketPath'."
    exit 0 # Exit successfully as there's nothing to do
}

$GlobalSuccess = $true # Track overall success

foreach ($ManifestFile in $ManifestFiles) {
    $AppName = $ManifestFile.BaseName
    Write-Output ""
    Write-Output "Processing: $AppName (File: $($ManifestFile.Name))"

    try {
        Write-Output "  Running 'scoop checkver `"$AppName`" -u'..."
        # Execute scoop checkver. The -u flag attempts to update the manifest file directly.
        # Capture all output streams to see what scoop does.
        $ProcessOutput = scoop checkver "$AppName" -u *>&1 
        
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "  'scoop checkver -u' for '$AppName' may have finished with warnings or an error (Exit Code: $LASTEXITCODE)."
            # We don't fail the script here, as some 'checkver' issues might be non-critical
            # or the app might not have a checkver method.
        } else {
            Write-Output "  'scoop checkver -u' for '$AppName' completed (or no update was found by checkver)."
        }
        # Print scoop checkver output regardless of exit code for logging
        if ($ProcessOutput) {
            Write-Output "  Output from scoop checkver for '$AppName':"
            $ProcessOutput | ForEach-Object { Write-Output "    $_" }
        }
    } catch {
        Write-Error "  An unexpected error occurred while running 'scoop checkver -u' for '$AppName': $($_.Exception.Message)"
        $GlobalSuccess = $false # Mark that at least one critical error occurred
    }
    Write-Output "---------------------------"
}

Write-Output ""
Write-Output "===================================================================="
if ($GlobalSuccess) {
    Write-Output "Manifest version and URL update process completed."
} else {
    Write-Warning "Manifest version and URL update process completed with some errors/warnings."
    # exit 1 # Optionally, exit with error if any critical step failed
}
