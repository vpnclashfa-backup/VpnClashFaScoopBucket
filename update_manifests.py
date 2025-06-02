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

## How to Use / scoop

```powershell
scoop bucket add {bucket_name_for_display} {repo_url_for_readme}
scoop install {bucket_name_for_display}/<program-name>
```

## Packages

{APP_LIST_START_PLACEHOLDER}
The list of applications will be populated here when the action runs next.
{APP_LIST_END_PLACEHOLDER}
"""
        try:
            readme_path.write_text(default_readme_content, encoding='utf-8')
            print(f"A sample README.md was created at '{readme_path}'.")
            readme_content_changed = True # README was created/changed
        except Exception as e:
            print(f"Error creating sample README.md: {e}")
            return False

    try:
        current_readme_content = readme_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading README.md content from '{readme_path}': {e}")
        return False # Cannot proceed if README cannot be read

    # Generate the new app list in the desired plain format
    app_list_plain_text = []
    if app_names:
        for app_name in sorted(app_names):
            app_list_plain_text.append(app_name)
    else:
        app_list_plain_text.append("No applications have been added to this bucket yet.")
    
    formatted_app_list_for_readme = "\n".join(app_list_plain_text)

    start_index = current_readme_content.find(APP_LIST_START_PLACEHOLDER)
    end_index = current_readme_content.find(APP_LIST_END_PLACEHOLDER)

    if start_index != -1 and end_index != -1 and end_index > start_index:
        content_before_list = current_readme_content[:start_index + len(APP_LIST_START_PLACEHOLDER)]
        if not content_before_list.endswith('\n'): # Ensure newline after start placeholder
            content_before_list += '\n'
        
        content_after_list = current_readme_content[end_index:]
        # Ensure newline before end placeholder
        effective_app_list = formatted_app_list_for_readme
        if not effective_app_list.endswith('\n'):
            effective_app_list += '\n'
            
        new_readme_content = f"{content_before_list}{effective_app_list}{content_after_list}"
        
        if new_readme_content != current_readme_content:
            try:
                readme_path.write_text(new_readme_content, encoding='utf-8')
                print("README.md was updated with the new list of applications.")
                readme_content_changed = True
            except Exception as e:
                print(f"Error updating README.md with the application list: {e}")
        else:
            print("README.md content (app list) is already up-to-date.")
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
        exit(1)

    manifest_files_paths = list(bucket_dir_path.glob("*.json"))
    processed_app_names_for_readme = []
    any_file_changed_in_run = False # Tracks if manifests or README changed

    if not manifest_files_paths:
        print(f"No manifest files (.json) found in '{bucket_dir_path}'.")
    else:
        for manifest_path in manifest_files_paths:
            app_name = manifest_path.stem
            print(f"\nProcessing manifest: {app_name} (File: {manifest_path.name})")
            print("---------------------------")
            manifest_data_object = None # Renamed
            
            print(f"Running 'scoop checkver \"{app_name}\" -u'...")
            try:
                checkver_command_args = ["pwsh", "-NoProfile", "-Command", f"scoop checkver '{app_name}' -u"] # Renamed
                checkver_run_result = subprocess.run( # Renamed
                    checkver_command_args, capture_output=True, text=True, check=False, encoding='utf-8', errors='replace'
                )
                if checkver_run_result.returncode != 0:
                    print(f"  Warning: Command `{' '.join(checkver_command_args)}` finished with exit code {checkver_run_result.returncode}.")
                    if checkver_run_result.stdout and checkver_run_result.stdout.strip(): print(f"    Scoop Checkver STDOUT:\n{checkver_run_result.stdout.strip()}")
                    if checkver_run_result.stderr and checkver_run_result.stderr.strip(): print(f"    Scoop Checkver STDERR:\n{checkver_run_result.stderr.strip()}")
                else:
                    print(f"  'scoop checkver -u' for '{app_name}' executed successfully (or no update was needed).")
                    if checkver_run_result.stdout and checkver_run_result.stdout.strip(): print(f"    Scoop Checkver Output:\n{checkver_run_result.stdout.strip()}")
            except FileNotFoundError:
                print("  Error: 'pwsh' (PowerShell) not found. Cannot run 'scoop checkver'.")
            except Exception as e:
                print(f"  Warning: Error during execution of 'scoop checkver \"{app_name}\" -u': {e}")

            try:
                with open(manifest_path, 'r', encoding='utf-8-sig') as f:
                    manifest_data_object = json.load(f)
            except Exception as e:
                print(f"  Error reading or parsing JSON manifest file '{manifest_path}': {e}")
                any_file_changed_in_run = True
                continue

            download_url_from_manifest = None; hash_from_manifest = None # Renamed
            json_hash_path_keys = [] # Renamed

            if manifest_data_object.get("architecture", {}).get("64bit", {}).get("url"):
                download_url_from_manifest = manifest_data_object["architecture"]["64bit"]["url"]
                hash_from_manifest = manifest_data_object["architecture"]["64bit"].get("hash")
                json_hash_path_keys = ["architecture", "64bit", "hash"]
            elif manifest_data_object.get("url"):
                download_url_from_manifest = manifest_data_object["url"]
                hash_from_manifest = manifest_data_object.get("hash")
                json_hash_path_keys = ["hash"]
            
            if not download_url_from_manifest:
                print(f"  Warning: 'url' field not found or empty in manifest '{app_name}'. Skipping hash update.")
                processed_app_names_for_readme.append(app_name)
                continue
            
            print(f"  Download URL found: {download_url_from_manifest}")
            print(f"  Current hash in manifest: {hash_from_manifest}")

            temp_download_folder = repo_root / "temp_scoop_downloads_python_v2" # Renamed
            temp_download_folder.mkdir(exist_ok=True)
            url_filename = os.path.basename(download_url_from_manifest.split('?')[0])
            safe_temp_filename = "".join(c if c.isalnum() or c in ['.', '-', '_'] else '_' for c in url_filename) # Renamed
            if not safe_temp_filename: safe_temp_filename = "downloaded_asset"
            path_to_temp_file = temp_download_folder / f"{app_name}_{safe_temp_filename}.tmp" # Renamed

            is_download_successful = download_file_from_url(download_url_from_manifest, path_to_temp_file) # Renamed
            calculated_new_hash = None # Renamed

            if is_download_successful:
                calculated_new_hash = calculate_sha256_hash(path_to_temp_file)
                if calculated_new_hash:
                    print(f"  New calculated hash for '{app_name}': {calculated_new_hash}")
            
            if path_to_temp_file.exists():
                os.remove(path_to_temp_file)
            if temp_download_folder.exists() and not any(temp_download_folder.iterdir()): # Remove if empty
                 temp_download_folder.rmdir()

            manifest_modified_by_hash_update = False # Renamed
            if calculated_new_hash and hash_from_manifest != calculated_new_hash:
                print(f"  New hash ({calculated_new_hash}) for '{app_name}' differs from current manifest hash ({hash_from_manifest}). Updating hash...")
                
                target_obj = manifest_data_object
                if json_hash_path_keys == ["architecture", "64bit", "hash"]:
                    if "architecture" in target_obj and "64bit" in target_obj["architecture"]:
                        target_obj["architecture"]["64bit"]["hash"] = calculated_new_hash
                        manifest_modified_by_hash_update = True
                elif json_hash_path_keys == ["hash"]:
                    if "hash" in target_obj or hash_from_manifest is not None : # Ensure key exists or was placeholder
                        target_obj["hash"] = calculated_new_hash
                        manifest_modified_by_hash_update = True
                
                if not manifest_modified_by_hash_update: # If path was not matched, or key didn't exist as expected
                     print(f"  Warning: Could not determine where to update hash in manifest '{app_name}'.")

            elif calculated_new_hash:
                print(f"  Calculated hash for '{app_name}' is identical to the hash in the manifest. No hash update needed.")
            else:
                print(f"  Hash for '{app_name}' was not updated due to previous download/calculation errors.")
                any_file_changed_in_run = True # Mark as issue

            if manifest_modified_by_hash_update:
                 try:
                    with open(manifest_path, 'w', encoding='utf-8') as f:
                        json.dump(manifest_data_object, f, indent=4, ensure_ascii=False)
                    print(f"  Manifest file '{app_name}' was successfully updated with the new hash.")
                    any_file_changed_in_run = True
                 except Exception as e:
                    print(f"  Error saving updated manifest file '{app_name}': {e}")
                    any_file_changed_in_run = True # Mark as issue
            
            processed_app_names_for_readme.append(app_name)
            print(f"Processing of manifest '{app_name}' finished.")
            print("---------------------------")

    # --- Update README.md ---
    repo_env_var_full_name = os.environ.get("GITHUB_REPOSITORY") # Renamed
    bucket_name_for_readme_display = "MyScoopBucket" # Default
    github_repo_address_for_readme = "YourUsername/YourRepoName" # Default

    if repo_env_var_full_name:
        repo_parts = repo_env_var_full_name.split('/') # Renamed
        if len(repo_parts) == 2:
            github_repo_address_for_readme = repo_env_var_full_name
            bucket_name_for_readme_display = repo_parts[1]
    else:
        try:
            git_origin_url_process = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=False, encoding='utf-8', errors='replace') # Renamed
            if git_origin_url_process.returncode == 0:
                parsed_remote_url = git_origin_url_process.stdout.strip() # Renamed
                url_match = re.search(r'github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?$', parsed_remote_url) # Renamed
                if url_match:
                    repo_owner, repo_actual_name = url_match.groups() # Renamed
                    github_repo_address_for_readme = f"{repo_owner}/{repo_actual_name}"
                    bucket_name_for_readme_display = repo_actual_name
                else:
                    print("Warning: Could not parse GitHub repository name from git remote URL for README.")
            else:
                print("Warning: 'git remote get-url origin' failed. Using default README info.")
        except Exception as e:
            print(f"Warning: Could not determine repository info from git for README: {e}. Using default README info.")

    readme_file_was_changed = update_readme_file(readme_file_path, processed_app_names_for_readme, bucket_name_for_readme_display, github_repo_address_for_readme) # Renamed

    print("\n=========================================================")
    if any_file_changed_in_run or readme_file_was_changed :
        print("Update operation completed. Some files may have been modified or errors occurred.")
    else:
        print("Update operation for all manifests completed successfully (or no changes were needed).")

if __name__ == "__main__":
    main()
