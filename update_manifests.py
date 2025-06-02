# update_manifests.py
import os
import json
import hashlib
import subprocess
import requests # External library, needs to be installed (e.g., pip install requests)
from pathlib import Path
import re # For parsing git remote URL

# --- Configuration ---
BUCKET_SUBDIRECTORY = "bucket"  # Subdirectory containing .json manifest files
README_FILE_NAME = "README.md"
APP_LIST_START_PLACEHOLDER = ""
APP_LIST_END_PLACEHOLDER = ""
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
REQUEST_TIMEOUT_SECONDS = 300 # Timeout for downloading files

def calculate_sha256_hash(file_path: Path) -> str | None:
    """Calculates the SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest().lower()
    except Exception as e:
        print(f"    Error calculating SHA256 for {file_path}: {e}")
        return None

def download_file_from_url(url: str, destination_path: Path) -> bool:
    """Downloads a file from a URL to a destination path."""
    print(f"    Downloading from: {url}")
    print(f"    Saving to: {destination_path}")
    try:
        headers = {"User-Agent": USER_AGENT}
        with requests.get(url, headers=headers, stream=True, timeout=REQUEST_TIMEOUT_SECONDS) as r:
            r.raise_for_status() # Raises an exception for bad status codes
            with open(destination_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"    Download successful: {destination_path.name}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"    Error downloading file from '{url}': {e}")
        return False
    except Exception as e:
        print(f"    An unexpected error occurred during download from '{url}': {e}")
        return False

def update_readme_file(readme_path: Path, app_names: list[str], bucket_name_for_display: str, github_repo_address: str):
    """Updates the README.md file with the list of applications."""
    print(f"\nUpdating README.md at: {readme_path}")
    repo_url_for_readme = f"https://github.com/{github_repo_address}.git"

    if not readme_path.exists():
        print(f"Warning: README.md not found at '{readme_path}'. Creating a sample README.md.")
        default_readme_content = f"""# Scoop Bucket: {bucket_name_for_display}

This is a personal Scoop bucket for easily installing software.

## How to Use

To add this bucket to Scoop, run the following command in PowerShell:

`scoop bucket add {bucket_name_for_display} {repo_url_for_readme}`

## Available Applications

{APP_LIST_START_PLACEHOLDER}
The list of applications will be populated here when the action runs next.
{APP_LIST_END_PLACEHOLDER}
"""
        try:
            readme_path.write_text(default_readme_content, encoding='utf-8')
            print(f"A sample README.md was created at '{readme_path}'.")
        except Exception as e:
            print(f"Error creating sample README.md: {e}")
            return

    try:
        readme_content = readme_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading README.md content from '{readme_path}': {e}")
        return

    app_list_markdown = ""
    if app_names:
        for app_name in sorted(app_names):
            app_list_markdown += f"- `{app_name}`\n"
    else:
        app_list_markdown = "No applications have been added to this bucket yet.\n"

    start_index = readme_content.find(APP_LIST_START_PLACEHOLDER)
    end_index = readme_content.find(APP_LIST_END_PLACEHOLDER)

    if start_index != -1 and end_index != -1 and end_index > start_index:
        content_before_list = readme_content[:start_index + len(APP_LIST_START_PLACEHOLDER)]
        content_after_list = readme_content[end_index:]
        new_readme_content = f"{content_before_list}\n{app_list_markdown}\n{content_after_list}"

        if new_readme_content != readme_content:
            try:
                readme_path.write_text(new_readme_content, encoding='utf-8')
                print("README.md was updated with the new list of applications.")
            except Exception as e:
                print(f"Error updating README.md with the application list: {e}")
        else:
            print("README.md content is already up-to-date.")
    else:
        print(f"Warning: Placeholders '{APP_LIST_START_PLACEHOLDER}' and/or '{APP_LIST_END_PLACEHOLDER}' not found in README.md.")
        print("The application list was not added to README.md. Please add the placeholders manually.")

def main():
    """Main function to process all manifests and update README."""
    repo_root = Path(".").resolve() # Assumes script is run from the repository root
    bucket_dir_path = repo_root / BUCKET_SUBDIRECTORY
    readme_file_path = repo_root / README_FILE_NAME

    print(f"Script to update manifests in '{bucket_dir_path}' started.")
    print("---------------------------------------------------------")

    if not bucket_dir_path.is_dir():
        print(f"Error: Bucket directory '{bucket_dir_path}' not found.")
        return

    manifest_files_paths = list(bucket_dir_path.glob("*.json"))
    processed_app_names = []
    any_file_changed_overall = False

    if not manifest_files_paths:
        print(f"No manifest files (.json) found in '{bucket_dir_path}'.")
    else:
        for manifest_path in manifest_files_paths:
            app_name = manifest_path.stem
            print(f"\nProcessing manifest: {app_name} (File: {manifest_path.name})")
            print("---------------------------")

            # 1. Run 'scoop checkver -u' to attempt automatic version/URL update
            print(f"Running 'scoop checkver \"{app_name}\" -u'...")
            try:
                # Using shell=True can be a security risk if app_name is not controlled.
                # For Windows runners in GitHub Actions, pwsh should be available.
                checkver_command = ["pwsh", "-Command", f"scoop checkver '{app_name}' -u"]
                checkver_process = subprocess.run(
                    checkver_command,
                    capture_output=True, text=True, check=False, encoding='utf-8', errors='replace'
                )
                if checkver_process.returncode != 0:
                    print(f"Warning: Command `{' '.join(checkver_command)}` finished with exit code {checkver_process.returncode}.")
                    if checkver_process.stdout: print(f"  Scoop Checkver STDOUT:\n{checkver_process.stdout.strip()}")
                    if checkver_process.stderr: print(f"  Scoop Checkver STDERR:\n{checkver_process.stderr.strip()}")
                else:
                    print(f"'scoop checkver -u' for '{app_name}' executed successfully (or no update was needed).")
                    if checkver_process.stdout: print(f"  Scoop Checkver Output:\n{checkver_process.stdout.strip()}")
            except FileNotFoundError:
                print("Error: 'pwsh' (PowerShell Core) or 'scoop' not found. Make sure Scoop is installed and in PATH.")
                # Potentially skip hash update if scoop checkver fails critically
            except Exception as e:
                print(f"Warning: Error during execution of 'scoop checkver \"{app_name}\" -u': {e}")

            # 2. Read manifest content (potentially updated by scoop checkver)
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest_data = json.load(f)
            except Exception as e:
                print(f"Error reading or parsing JSON manifest file '{manifest_path}': {e}")
                any_file_changed_overall = True # Mark as potential issue
                continue

            # 3. Extract download URL and current hash
            download_url = None
            current_hash_in_manifest = None
            is_64bit_architecture_present = False

            if "architecture" in manifest_data and "64bit" in manifest_data["architecture"] and "url" in manifest_data["architecture"]["64bit"]:
                download_url = manifest_data["architecture"]["64bit"]["url"]
                current_hash_in_manifest = manifest_data["architecture"]["64bit"].get("hash")
                is_64bit_architecture_present = True
            elif "url" in manifest_data:
                download_url = manifest_data["url"]
                current_hash_in_manifest = manifest_data.get("hash")

            if not download_url:
                print(f"Warning: 'url' field not found or empty in manifest '{app_name}'. Skipping hash update for this file.")
                processed_app_names.append(app_name) # Still add to README list
                continue

            print(f"  Download URL found: {download_url}")
            print(f"  Current hash in manifest: {current_hash_in_manifest}")

            # 4. Download file to a temporary path
            temp_download_dir = repo_root / "temp_scoop_downloads"
            temp_download_dir.mkdir(exist_ok=True)
            # Sanitize filename from URL slightly for temp file
            url_filename_part = os.path.basename(download_url.split('?')[0]) # Get filename before query params
            safe_filename = "".join(c if c.isalnum() or c in ['.', '-', '_'] else '_' for c in url_filename_part)
            temp_file_path = temp_download_dir / f"{app_name}_{safe_filename}.tmp"

            download_successful = download_file_from_url(download_url, temp_file_path)

            newly_calculated_hash = None
            if download_successful:
                newly_calculated_hash = calculate_sha256_hash(temp_file_path)
                if newly_calculated_hash:
                    print(f"  New calculated hash for '{app_name}': {newly_calculated_hash}")

            if temp_file_path.exists():
                os.remove(temp_file_path) # Clean up temp file
            if not any(temp_download_dir.iterdir()): # Clean up temp dir if empty
                temp_download_dir.rmdir()


            # 5. Compare and update manifest hash if necessary
            manifest_hash_updated_this_run = False
            if newly_calculated_hash and current_hash_in_manifest != newly_calculated_hash:
                print(f"  New hash ({newly_calculated_hash}) for '{app_name}' differs from current manifest hash ({current_hash_in_manifest}). Updating hash...")
                if is_64bit_architecture_present:
                    manifest_data["architecture"]["64bit"]["hash"] = newly_calculated_hash
                elif "hash" in manifest_data or current_hash_in_manifest is not None : # Only update if hash key exists or was placeholder
                    manifest_data["hash"] = newly_calculated_hash
                else: # Should not happen if placeholder was there
                    print(f"  Warning: 'hash' key not found in expected location in manifest '{app_name}'. Hash not updated.")

                try:
                    with open(manifest_path, 'w', encoding='utf-8') as f:
                        json.dump(manifest_data, f, indent=4, ensure_ascii=False) # Using indent=4 for pretty JSON
                    print(f"  Manifest file '{app_name}' was successfully updated with the new hash.")
                    manifest_hash_updated_this_run = True
                    any_file_changed_overall = True
                except Exception as e:
                    print(f"  Error saving updated manifest file '{app_name}': {e}")
                    any_file_changed_overall = True # Mark as potential issue
            elif newly_calculated_hash: # Hash is same
                print(f"  Calculated hash for '{app_name}' is identical to the hash in the manifest. No hash update needed.")
            else: # Hash calculation failed or download failed
                print(f"  Hash for '{app_name}' was not updated due to previous errors.")
                any_file_changed_overall = True # Mark as potential issue

            processed_app_names.append(app_name)
            print(f"Processing of manifest '{app_name}' finished.")
            print("---------------------------")

    # --- Update README.md ---
    github_repo_env_var = os.environ.get("GITHUB_REPOSITORY")
    user_display_bucket_name = "MyScoopBucket" # Default
    repo_full_address = "YourUsername/YourRepoName" # Default

    if github_repo_env_var:
        parts = github_repo_env_var.split('/')
        if len(parts) == 2:
            repo_full_address = github_repo_env_var
            user_display_bucket_name = parts[1]
    else: # Try to get from local git remote
        try:
            git_remote_process = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=False, encoding='utf-8')
            if git_remote_process.returncode == 0:
                remote_url = git_remote_process.stdout.strip()
                match = re.search(r'github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?$', remote_url)
                if match:
                    owner, repo_name = match.groups()
                    repo_full_address = f"{owner}/{repo_name}"
                    user_display_bucket_name = repo_name
                else:
                    print("Warning: Could not parse GitHub repository name from git remote URL.")
            else:
                print("Warning: 'git remote get-url origin' failed. Using default README info.")
        except Exception as e:
            print(f"Warning: Could not determine repository info from git: {e}. Using default README info.")

    update_readme_file(readme_file_path, processed_app_names, user_display_bucket_name, repo_full_address)

    print("\n=========================================================")
    if any_file_changed_overall:
        print("Update operation completed. Some files may have been modified or errors occurred.")
        # In a GitHub Action, the subsequent commit step will handle changed files.
        # If running locally, user should review and commit changes.
    else:
        print("Update operation for all manifests completed successfully (or no changes were needed).")

if __name__ == "__main__":
    main()
