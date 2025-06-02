# update_manifests.py
import os
import json
import hashlib
import subprocess
import requests
from pathlib import Path
import re

# --- Configuration ---
BUCKET_SUBDIRECTORY = "bucket"
README_FILE_NAME = "README.md"
APP_LIST_START_PLACEHOLDER = ""
APP_LIST_END_PLACEHOLDER = ""
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
REQUEST_TIMEOUT_SECONDS = 300

def calculate_sha256_hash(file_path: Path) -> str | None:
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest().lower()
    except Exception as e:
        print(f"    Error calculating SHA256 for {file_path.name}: {e}")
        return None

def download_file_from_url(url: str, destination_path: Path) -> bool:
    print(f"    Downloading from: {url}")
    print(f"    Saving to: {destination_path.name}")
    try:
        headers = {"User-Agent": USER_AGENT}
        with requests.get(url, headers=headers, stream=True, timeout=REQUEST_TIMEOUT_SECONDS) as r:
            r.raise_for_status()
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
    print(f"\nUpdating README.md at: {readme_path}")
    repo_url_for_readme = f"https://github.com/{github_repo_address}.git"
    readme_content_changed = False

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
            return True # Indicate that README was changed (created)
        except Exception as e:
            print(f"Error creating sample README.md: {e}")
            return False

    try:
        current_readme_content = readme_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading README.md content from '{readme_path}': {e}")
        return False

    app_list_markdown = ""
    if app_names:
        for app_name in sorted(app_names):
            app_list_markdown += f"- `{app_name}`\n"
    else:
        app_list_markdown = "No applications have been added to this bucket yet.\n"

    start_index = current_readme_content.find(APP_LIST_START_PLACEHOLDER)
    end_index = current_readme_content.find(APP_LIST_END_PLACEHOLDER)

    if start_index != -1 and end_index != -1 and end_index > start_index:
        content_before_list = current_readme_content[:start_index + len(APP_LIST_START_PLACEHOLDER)]
        # Ensure there's a newline after the start placeholder in the new content
        if not content_before_list.endswith('\n'):
            content_before_list += '\n'
        
        content_after_list = current_readme_content[end_index:]
        # Ensure there's a newline before the end placeholder if the app list is not empty
        # or ensure there is if it is empty
        if app_list_markdown.strip() == "" or app_list_markdown.endswith('\n'):
             middle_content = app_list_markdown
        else:
             middle_content = app_list_markdown + '\n'

        new_readme_content = f"{content_before_list}{middle_content}{content_after_list}"
        
        if new_readme_content != current_readme_content:
            try:
                readme_path.write_text(new_readme_content, encoding='utf-8')
                print("README.md was updated with the new list of applications.")
                readme_content_changed = True
            except Exception as e:
                print(f"Error updating README.md with the application list: {e}")
        else:
            print("README.md content is already up-to-date.")
    else:
        print(f"Warning: Placeholders '{APP_LIST_START_PLACEHOLDER}' and/or '{APP_LIST_END_PLACEHOLDER}' not found in README.md.")
        print("The application list was not added to README.md. Please add the placeholders manually.")
    
    return readme_content_changed

def main():
    repo_root = Path(".").resolve()
    bucket_dir_path = repo_root / BUCKET_SUBDIRECTORY
    readme_file_path = repo_root / README_FILE_NAME

    print(f"Script to update manifests in '{bucket_dir_path}' started.")
    print("---------------------------------------------------------")

    if not bucket_dir_path.is_dir():
        print(f"Error: Bucket directory '{bucket_dir_path}' not found.")
        exit(1) # Exit with error if bucket dir not found

    manifest_files_paths = list(bucket_dir_path.glob("*.json"))
    processed_app_names = []
    any_manifest_file_updated_in_run = False

    if not manifest_files_paths:
        print(f"No manifest files (.json) found in '{bucket_dir_path}'.")
    else:
        for manifest_path in manifest_files_paths:
            app_name = manifest_path.stem
            print(f"\nProcessing manifest: {app_name} (File: {manifest_path.name})")
            print("---------------------------")
            manifest_data = None
            
            # 1. Run 'scoop checkver -u'
            print(f"Running 'scoop checkver \"{app_name}\" -u'...")
            try:
                checkver_command = ["pwsh", "-NoProfile", "-Command", f"scoop checkver '{app_name}' -u"]
                checkver_process = subprocess.run(
                    checkver_command, capture_output=True, text=True, check=False, encoding='utf-8', errors='replace'
                )
                if checkver_process.returncode != 0:
                    print(f"  Warning: Command `{' '.join(checkver_command)}` finished with exit code {checkver_process.returncode}.")
                    if checkver_process.stdout and checkver_process.stdout.strip(): print(f"    Scoop Checkver STDOUT:\n{checkver_process.stdout.strip()}")
                    if checkver_process.stderr and checkver_process.stderr.strip(): print(f"    Scoop Checkver STDERR:\n{checkver_process.stderr.strip()}")
                else:
                    print(f"  'scoop checkver -u' for '{app_name}' executed successfully (or no update was needed).")
                    if checkver_process.stdout and checkver_process.stdout.strip(): print(f"    Scoop Checkver Output:\n{checkver_process.stdout.strip()}")
            except FileNotFoundError:
                print("  Error: 'pwsh' (PowerShell) not found. Cannot run 'scoop checkver'.")
            except Exception as e:
                print(f"  Warning: Error during execution of 'scoop checkver \"{app_name}\" -u': {e}")

            # 2. Read manifest content
            try:
                with open(manifest_path, 'r', encoding='utf-8-sig') as f: # Use utf-8-sig to handle BOM
                    manifest_data = json.load(f)
            except Exception as e:
                print(f"  Error reading or parsing JSON manifest file '{manifest_path}': {e}")
                continue

            # 3. Extract download URL and current hash
            download_url = None
            current_hash_in_manifest = None
            hash_path_in_json = [] # To know where to update the hash

            if manifest_data.get("architecture", {}).get("64bit", {}).get("url"):
                download_url = manifest_data["architecture"]["64bit"]["url"]
                current_hash_in_manifest = manifest_data["architecture"]["64bit"].get("hash")
                hash_path_in_json = ["architecture", "64bit", "hash"]
            elif manifest_data.get("url"):
                download_url = manifest_data["url"]
                current_hash_in_manifest = manifest_data.get("hash")
                hash_path_in_json = ["hash"]
            
            if not download_url:
                print(f"  Warning: 'url' field not found or empty in manifest '{app_name}'. Skipping hash update for this file.")
                processed_app_names.append(app_name)
                continue
            
            print(f"  Download URL found: {download_url}")
            print(f"  Current hash in manifest: {current_hash_in_manifest}")

            # 4. Download file
            temp_download_dir = repo_root / "temp_scoop_downloads_py" # Unique temp dir name
            temp_download_dir.mkdir(exist_ok=True)
            url_filename_part = os.path.basename(download_url.split('?')[0])
            safe_filename = "".join(c if c.isalnum() or c in ['.', '-', '_'] else '_' for c in url_filename_part)
            if not safe_filename: safe_filename = "downloaded_file" # Fallback if basename is strange
            temp_file_path = temp_download_dir / f"{app_name}_{safe_filename}.tmp"

            download_successful = download_file_from_url(download_url, temp_file_path)
            newly_calculated_hash = None

            if download_successful:
                newly_calculated_hash = calculate_sha256_hash(temp_file_path)
                if newly_calculated_hash:
                    print(f"  New calculated hash for '{app_name}': {newly_calculated_hash}")
            
            if temp_file_path.exists():
                os.remove(temp_file_path)
            if temp_download_dir.exists() and not any(temp_download_dir.iterdir()):
                 temp_download_dir.rmdir()

            # 5. Compare and update manifest hash
            if newly_calculated_hash and current_hash_in_manifest != newly_calculated_hash:
                print(f"  New hash ({newly_calculated_hash}) for '{app_name}' differs from current manifest hash ({current_hash_in_manifest}). Updating hash...")
                
                # Update hash in the manifest_data object
                if hash_path_in_json == ["architecture", "64bit", "hash"]:
                    manifest_data["architecture"]["64bit"]["hash"] = newly_calculated_hash
                elif hash_path_in_json == ["hash"]:
                    manifest_data["hash"] = newly_calculated_hash
                else: # Should not happen if hash was found earlier
                    print(f"  Warning: Could not determine where to update hash in manifest '{app_name}'.")
                    processed_app_names.append(app_name)
                    continue # Skip saving this manifest

                try:
                    with open(manifest_path, 'w', encoding='utf-8') as f: # Save as UTF-8 (no BOM by default)
                        json.dump(manifest_data, f, indent=4, ensure_ascii=False)
                    print(f"  Manifest file '{app_name}' was successfully updated with the new hash.")
                    any_manifest_file_updated_in_run = True
                except Exception as e:
                    print(f"  Error saving updated manifest file '{app_name}': {e}")
            elif newly_calculated_hash:
                print(f"  Calculated hash for '{app_name}' is identical to the hash in the manifest. No hash update needed.")
            else:
                print(f"  Hash for '{app_name}' was not updated due to previous download/calculation errors.")

            processed_app_names.append(app_name)
            print(f"Processing of manifest '{app_name}' finished.")
            print("---------------------------")

    # --- Update README.md ---
    github_repo_env_var = os.environ.get("GITHUB_REPOSITORY")
    user_display_bucket_name = "MyScoopBucket"
    repo_full_address_for_readme = "YourUsername/YourRepoName"

    if github_repo_env_var:
        parts = github_repo_env_var.split('/')
        if len(parts) == 2:
            repo_full_address_for_readme = github_repo_env_var
            user_display_bucket_name = parts[1]
    else:
        try:
            git_remote_process = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=False, encoding='utf-8', errors='replace')
            if git_remote_process.returncode == 0:
                remote_url = git_remote_process.stdout.strip()
                match = re.search(r'github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?$', remote_url)
                if match:
                    owner, repo_name = match.groups()
                    repo_full_address_for_readme = f"{owner}/{repo_name}"
                    user_display_bucket_name = repo_name
                else:
                    print("Warning: Could not parse GitHub repository name from git remote URL for README.")
            else:
                print("Warning: 'git remote get-url origin' failed. Using default README info.")
        except Exception as e:
            print(f"Warning: Could not determine repository info from git for README: {e}. Using default README info.")

    readme_was_changed = update_readme_file(readme_file_path, processed_app_names, user_display_bucket_name, repo_full_address_for_readme)

    print("\n=========================================================")
    if any_manifest_file_updated_in_run or readme_was_changed :
        print("Update operation completed. Some files were modified.")
    else:
        print("Update operation for all manifests completed successfully (no changes were needed).")

if __name__ == "__main__":
    main()