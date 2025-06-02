# Update-ScoopVersions.ps1
[CmdletBinding()]
param (
    [Parameter(Mandatory=$false)]
    [string]$BucketPath = "./bucket",

    [Parameter(Mandatory=$true)] 
    [string]$ProvidedScoopShimsPath 
)

Write-Output "Script Version: v11_try_scoop_cmd"
Write-Output "Provided BucketPath: $BucketPath"
Write-Output "Provided ScoopShimsPath from workflow: $ProvidedScoopShimsPath"

$ScoopCmdPath = $null

# Step 1: Construct the explicit path to scoop.cmd
if (-not [string]::IsNullOrWhiteSpace($ProvidedScoopShimsPath)) {
    if (Test-Path $ProvidedScoopShimsPath -PathType Container) {
        $PotentialScoopCmd = Join-Path $ProvidedScoopShimsPath "scoop.cmd"
        Write-Output "Testing for scoop.cmd at: '$PotentialScoopCmd'"
        if (Test-Path $PotentialScoopCmd -PathType Leaf) {
            $ScoopCmdPath = $PotentialScoopCmd
            Write-Output "SUCCESS: scoop.cmd found at explicit path: $ScoopCmdPath"
        } else {
            Write-Error "CRITICAL FAILURE: scoop.cmd NOT FOUND as a file at '$PotentialScoopCmd'."
            Write-Output "Listing contents of '$ProvidedScoopShimsPath' for debugging:"
            Get-ChildItem -Path $ProvidedScoopShimsPath | ForEach-Object { Write-Output "  - $($_.Name) (Type: $($_.GetType().Name))" }
            exit 1
        }
    } else {
        Write-Error "CRITICAL: Provided Scoop Shims Path '$ProvidedScoopShimsPath' does NOT exist or is not a directory."
        exit 1
    }
} else {
    Write-Error "CRITICAL: No ScoopShimsPath was provided to the script. This is required."
    exit 1
}

# Optional: Ensure $env:SCOOP is set, as scoop.cmd might rely on it internally
$env:SCOOP = Split-Path $ProvidedScoopShimsPath
Write-Output "Ensured \$env:SCOOP is set to: $($env:SCOOP)"
# Optional: Ensure shims path is in PATH for the cmd process, though direct call should work
if ($env:PATH -notlike "*$ProvidedScoopShimsPath*") {
    $env:PATH = "$ProvidedScoopShimsPath;$($env:PATH)"
    Write-Output "Prepended '$ProvidedScoopShimsPath' to this script's session PATH (for cmd context)."
}
Write-Output "--------------------------------------------------------------------"

$ManifestFiles = Get-ChildItem -Path $BucketPath -Filter "*.json" -File -ErrorAction SilentlyContinue
if (-not $ManifestFiles) {
    Write-Warning "No manifest files (.json) found in '$BucketPath'."
    exit 0 
}

$GlobalSuccess = $true 
foreach ($ManifestFileItem in $ManifestFiles) {
    $AppName = $ManifestFileItem.BaseName
    Write-Output "" 
    Write-Output "Processing: $AppName (File: $($ManifestFileItem.Name))"
    try {
        # Execute scoop.cmd directly
        $CommandToRun = "$ScoopCmdPath checkver `"$AppName`" -u"
        Write-Output "  Running command: $CommandToRun"
        
        # Invoke using cmd.exe /c to ensure it runs in a cmd context
        # Capture output and errors
        $Process = Start-Process cmd.exe -ArgumentList "/c $CommandToRun" -Wait -NoNewWindow -PassThru -RedirectStandardOutput "stdout.log" -RedirectStandardError "stderr.log"
        
        $StdOut = Get-Content "stdout.log" -ErrorAction SilentlyContinue
        $StdErr = Get-Content "stderr.log" -ErrorAction SilentlyContinue
        Remove-Item "stdout.log", "stderr.log" -ErrorAction SilentlyContinue

        $ExitCode = $Process.ExitCode
        Write-Output "  scoop.cmd process exited with code: $ExitCode"

        if ($StdOut) {
            Write-Output "  Standard Output from scoop.cmd:"
            $StdOut | ForEach-Object { Write-Output "    $_" }
        }
        if ($StdErr) {
            Write-Warning "  Standard Error from scoop.cmd:"
            $StdErr | ForEach-Object { Write-Warning "    $_" }
        }
        
        # Check for the specific warning from Scoop itself
        if (($StdOut -join "`n" -match "isn't a scoop command") -or ($StdErr -join "`n" -match "isn't a scoop command")) {
             Write-Warning "  Scoop (via cmd) reported 'checkver' is not a command for '$AppName'."
             # Optionally set $GlobalSuccess = $false or handle as a specific type of failure
        } elseif ($ExitCode -ne 0) {
            Write-Warning "  scoop.cmd checkver for '$AppName' finished with a non-zero Exit Code: $ExitCode."
        } else {
            Write-Output "  scoop.cmd checkver for '$AppName' completed (Exit Code: 0)."
        }

    } catch {
        Write-Error "  An UNEXPECTED PowerShell error occurred while trying to run scoop.cmd for '$AppName': $($_.Exception.Message)"
        $GlobalSuccess = $false 
    }
    Write-Output "---------------------------" 
}

Write-Output "" 
Write-Output "===================================================================="
if ($GlobalSuccess) {
    Write-Output "Manifest version and URL update process completed its run."
} else {
    Write-Warning "Manifest version and URL update process encountered UNEXPECTED SCRIPT errors or scoop.cmd failures."
}
Write-Output "Script Update-ScoopVersions.ps1 (v11_try_scoop_cmd) finished."
