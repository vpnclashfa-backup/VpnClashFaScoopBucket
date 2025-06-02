# Update-AppVersionsAndUrls.py
import os
import json
import requests
from pathlib import Path
import re
from packaging.version import parse as parse_version 

# --- Configuration ---
BUCKET_PATH_STR = "bucket" 
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
REQUEST_TIMEOUT_SECONDS = 30 
CONFIG_FILE_NAME = "apps_config.json" 

# --- GitHub API Configuration ---
# Read the token from the environment variable set by the GitHub Actions workflow
# The workflow will set GH_API_TOKEN using secrets.SCOOP_UPDATER_PAT
GITHUB_API_TOKEN = os.environ.get("GH_API_TOKEN") 
                                    
GITHUB_API_HEADERS = {"Accept": "application/vnd.github.v3+json"}
if GITHUB_API_TOKEN:
    print("[INFO] GitHub API token (GH_API_TOKEN) found. Using it for authenticated requests.")
    GITHUB_API_HEADERS["Authorization"] = f"token {GITHUB_API_TOKEN}"
else:
    print("[WARNING] GitHub API token (GH_API_TOKEN) not found in environment. Making unauthenticated requests (may hit rate limits).")

def load_apps_config(config_file_path: Path) -> list:
    """Loads the application configuration from a JSON file."""
    if not config_file_path.exists():
        print(f"[ERROR] Configuration file '{config_file_path}' not found.")
        return []
    try:
        with open(config_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Could not read or parse configuration file '{config_file_path}': {e}")
        return []

def get_github_releases_info(repo_owner_slash_repo: str) -> list | None:
    """Fetches all release information from GitHub API."""
    api_url = f"https://api.github.com/repos/{repo_owner_slash_repo}/releases"
    print(f"    Fetching releases from: {api_url}")
    try:
        response = requests.get(api_url, headers=GITHUB_API_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status() 
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"    [ERROR] Fetching releases for {repo_owner_slash_repo}: {e}")
        return None

def find_asset_by_keywords(assets: list, keywords: list) -> dict | None:
    """Finds an asset that contains all specified keywords in its name."""
    print(f"      Searching for asset with keywords: {keywords} in {len(assets)} assets.")
    for asset in assets:
        name_lower = asset.get("name", "").lower()
        if all(keyword.lower() in name_lower for keyword in keywords):
            print(f"      [SUCCESS] Found asset by keywords: {asset['name']}")
            return asset
    print(f"      [INFO] No asset found matching all keywords: {keywords}")
    return None

def clean_version_from_tag(tag_name: str, prefix: str = "") -> str:
    """Cleans the version string from a git tag."""
    cleaned_version = tag_name
    if prefix and tag_name.startswith(prefix):
        cleaned_version = tag_name[len(prefix):]
    
    # Additional cleaning for common cases like leading/trailing spaces or non-version chars
    cleaned_version = cleaned_version.strip()
    # Attempt to match a standard version pattern (e.g., X.Y.Z, X.Y.Z-beta, etc.)
    # This helps remove any unexpected trailing characters after a valid version string.
    version_match = re.match(r"(\d+(\.\d+)*([-.].+)?)", cleaned_version)
    if version_match:
        cleaned_version = version_match.group(1)
        
    # print(f"        Original tag: '{tag_name}', Prefix: '{prefix}', Cleaned version: '{cleaned_version}'") # Verbose
    return cleaned_version

def main():
    repo_root = Path(".").resolve()
    bucket_path_obj = repo_root / BUCKET_PATH_STR
    config_file_path_obj = repo_root / CONFIG_FILE_NAME
    
    print(f"Python script 'Update-AppVersionsAndUrls.py' started.")
    print(f"Loading app configurations from: '{config_file_path_obj}'")
    
    apps_config = load_apps_config(config_file_path_obj)
    if not apps_config:
        print("[CRITICAL] No application configurations loaded. Exiting.")
        exit(1)
            
    print(f"Successfully loaded {len(apps_config)} app configurations.")
    print(f"Processing manifests in: '{bucket_path_obj}'")
    print("--- Checking for new versions and updating manifests (version, URL) ---")

    manifests_updated_count = 0

    for app_config in apps_config:
        manifest_filename = app_config.get("manifest_file")
        repo_path = app_config.get("repo")
        asset_keywords = app_config.get("asset_keywords", [])
        version_strip_prefix = app_config.get("version_strip_prefix", "")
        allow_prerelease = app_config.get("allow_prerelease", False)

        if not manifest_filename or not repo_path:
            print(f"\n[WARNING] Skipping invalid app config entry: {app_config} (missing 'manifest_file' or 'repo')")
            continue
                
        manifest_full_path = bucket_path_obj / manifest_filename
        app_name = manifest_full_path.stem

        print(f"\nProcessing app: {app_name} (Manifest: {manifest_filename})")

        if not manifest_full_path.exists():
            print(f"  [WARNING] Manifest file '{manifest_filename}' not found. Skipping.")
            continue

        try:
            with open(manifest_full_path, 'r', encoding='utf-8-sig') as f:
                manifest_data = json.load(f)
        except Exception as e:
            print(f"  [ERROR] Could not read or parse manifest '{manifest_filename}': {e}")
            continue

        current_version_str_from_manifest = manifest_data.get("version", "0.0.0")
        
        all_releases = get_github_releases_info(repo_path)
        if not all_releases:
            print(f"  [INFO] Could not fetch release info for {repo_path}. Skipping version check for this app.")
            continue

        latest_release_to_consider = None
        for release in all_releases:
            is_prerelease = release.get("prerelease", False)
            if not allow_prerelease and is_prerelease:
                # print(f"    Skipping prerelease: {release.get('tag_name')}") # Verbose
                continue 
            latest_release_to_consider = release 
            break 
        
        if not latest_release_to_consider:
            if allow_prerelease and all_releases: 
                 latest_release_to_consider = all_releases[0]
                 print(f"  [INFO] No stable release found, considering latest prerelease: {latest_release_to_consider.get('tag_name')} for {repo_path}.")
            else:
                print(f"  [INFO] No suitable release (matching allow_prerelease={allow_prerelease}) found for {repo_path}. Skipping.")
                continue

        latest_tag_name_from_github = latest_release_to_consider.get("tag_name")
        if not latest_tag_name_from_github:
            print(f"  [INFO] No tag_name found in the selected release for {repo_path}. Skipping.")
            continue
        
        cleaned_latest_version_from_github = clean_version_from_tag(latest_tag_name_from_github, version_strip_prefix)
        print(f"  Current manifest version: {current_version_str_from_manifest}, Latest GitHub tag: {latest_tag_name_from_github} (Cleaned to: {cleaned_latest_version_from_github})")

        try:
            if not cleaned_latest_version_from_github: # Should not happen if tag_name exists
                print(f"  [WARNING] Cleaned version string is empty for tag '{latest_tag_name_from_github}'. Skipping comparison.")
                continue

            # Robust version comparison
            parsed_latest_version = parse_version(cleaned_latest_version_from_github)
            parsed_current_version = parse_version(current_version_str_from_manifest)

            if parsed_latest_version > parsed_current_version:
                print(f"  [UPDATE] Newer version found: {cleaned_latest_version_from_github} > {current_version_str_from_manifest}")
                
                assets = latest_release_to_consider.get("assets", [])
                if not assets:
                    print(f"    [WARNING] No assets found in release {latest_tag_name_from_github}. Cannot update URL.")
                    continue

                selected_asset = find_asset_by_keywords(assets, asset_keywords)
                
                if selected_asset and selected_asset.get("browser_download_url"):
                    new_url = selected_asset["browser_download_url"]
                    print(f"    New asset URL selected: {new_url}")

                    manifest_data["version"] = cleaned_latest_version_from_github # Use the cleaned version
                    
                    updated_url_field = False
                    if "architecture" in manifest_data and "64bit" in manifest_data["architecture"] and "url" in manifest_data["architecture"]["64bit"]:
                        manifest_data["architecture"]["64bit"]["url"] = new_url
                        manifest_data["architecture"]["64bit"]["hash"] = "" 
                        updated_url_field = True
                        print(f"    Updated 64bit URL and cleared hash.")
                    elif "url" in manifest_data: 
                        manifest_data["url"] = new_url
                        manifest_data["hash"] = "" 
                        updated_url_field = True
                        print(f"    Updated root URL and cleared hash.")
                    
                    if not updated_url_field:
                        print(f"    [WARNING] Could not find a standard 'url' field to update in manifest for {app_name}.")
                        continue 

                    try:
                        with open(manifest_full_path, 'w', encoding='utf-8') as f:
                            json.dump(manifest_data, f, indent=4, ensure_ascii=False)
                            f.write('\n')
                        print(f"    [SUCCESS] Manifest for {app_name} updated to version {cleaned_latest_version_from_github}. Hash cleared.")
                        manifests_updated_count += 1
                    except Exception as e:
                        print(f"    [ERROR] Could not write updated manifest for {app_name}: {e}")
                else:
                    print(f"    [WARNING] No suitable download asset found for version {cleaned_latest_version_from_github} using keywords: {asset_keywords}")
            else:
                print(f"  [INFO] {app_name} is already up-to-date or latest GitHub version ({cleaned_latest_version_from_github}) is not newer than manifest ({current_version_str_from_manifest}).")
        
        except packaging.version.InvalidVersion: # Catch specific error for invalid version strings
             print(f"  [ERROR] Invalid version string encountered for comparison: Current='{current_version_str_from_manifest}', Latest='{cleaned_latest_version_from_github}' for app {app_name}. Skipping.")
        except Exception as e: 
            print(f"  [ERROR] During version comparison or asset finding for {app_name}: {e}")

    print("\n=========================================================")
    if manifests_updated_count > 0:
        print(f"Script finished. {manifests_updated_count} manifest(s) had their version/URL updated (hash cleared).")
    else:
        print("Script finished. No manifest versions/URLs needed updating (or errors occurred).")
    print("Reminder: The other Python script should now run to update hashes and README.")

if __name__ == "__main__":
    main()
