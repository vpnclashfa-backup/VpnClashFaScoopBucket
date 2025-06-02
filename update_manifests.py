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
README_FILE_NAME = "README.md" # Name of your README file
APP_LIST_START_PLACEHOLDER = ""
APP_LIST_END_PLACEHOLDER = ""
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
REQUEST_TIMEOUT_SECONDS = 300

def calculate_sha256_hash(file_path: Path) -> str | None:
    """Calculates the SHA256 hash of a file."""
    sha256_hash_obj = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash_obj.update(byte_block)
        return sha256_hash_obj.hexdigest().lower()
    except Exception as e:
        print(f"    Error calculating SHA256 for {file_path.name}: {e}")
        return None

def download_file_from_url(url: str, destination_path: Path) -> bool:
    """Downloads a file from a URL to a destination path."""
    print(f"    Downloading from: {url}")
    print(f"    Saving to temporary file: {destination_path.name}")
    try:
        headers = {"User-Agent": USER_AGENT}
        with requests.get(url, headers=headers, stream=True, timeout=REQUEST_TIMEOUT_SECONDS) as r:
            r.raise_for_status() # Raises an exception for bad status codes (4xx or 5xx)
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

def update_readme_content(readme_path: Path, app_names: list[str]) -> bool:
    """Updates the README.md file with the list of applications between placeholders."""
    print(f"\nAttempting to update README.md at: {readme_path}")
    readme_content_changed_flag = False

    if not readme_path.exists():
        print(f"Warning: README.md not found at '{readme_path}'. Cannot update app list.")
        print(f"Please create a README.md file in the repository root with the placeholders: \n{APP_LIST_START_PLACEHOLDER}\n...app list...\n{APP_LIST_END_PLACEHOLDER}")
        return False

    try:
        current_readme_text = readme_path.read_text(encoding='utf-8') # Renamed variable
    except Exception as e:
        print(f"Error reading README.md content from '{readme_path}': {e}")
        return False

    # Generate the new app list in the desired plain format (each app on a new line)
    app_list_for_readme = [] # Renamed variable
    if app_names:
        for app_name_entry in sorted(app_names): # Renamed variable
            app_list_for_readme.append(app_name_entry)
    else:
        app_list_for_readme.append("(No applications currently listed in the bucket)") # English placeholder for empty list
    
    formatted_app_list_text = "\n".join(app_list_for_readme) # Renamed variable

    start_placeholder_index = current_readme_text.find(APP_LIST_START_PLACEHOLDER) # Renamed variable
    end_placeholder_index = current_readme_text.find(APP_LIST_END_PLACEHOLDER) # Renamed variable

    if start_placeholder_index != -1 and end_placeholder_index != -1 and end_placeholder_index > start_placeholder_index:
        text_before_list = current_readme_text[:start_placeholder_index + len(APP_LIST_START_PLACEHOLDER)] # Renamed variable
        if not text_before_list.endswith(('\n', '\r\n')):
            text_before_list += '\n'
        
        text_after_list = current_readme_text[end_placeholder_index:] # Renamed variable
        
        # Ensure the list itself ends with a newline before the end placeholder
        final_app_list_text = formatted_app_list_text
        if not final_app_list_text.endswith(('\n', '\r\n')):
            final_app_list_text += '\n'
            
        updated_readme_text = f"{text_before_list}{final_app_list_text}{text_after_list}" # Renamed variable
        
        if updated_readme_text != current_readme_text:
            try:
                readme_path.write_text(updated_readme_text, encoding='utf-8')
                print("README.md was updated with the new list of applications.")
                readme_content_changed_flag = True
            except Exception as e:
                print(f"Error writing updated README.md: {e}")
        else:
            print("README.md application list is already up-to-date.")
    else:
        print(f"Warning: Placeholders '{APP_LIST_START_PLACEHOLDER}' and/or '{APP_LIST_END_PLACEHOLDER}' not found in README.md.")
        print("The application list was not updated. Please add the placeholders to your README.md file.")
    
    return readme_content_changed_flag

def main():
    repo_root_dir = Path(".").resolve() # Renamed variable
    actual_bucket_dir = repo_root_dir / BUCKET_SUBDIRECTORY # Renamed variable
    actual_readme_file_path = repo_root_dir / README_FILE_NAME # Renamed variable

    print(f"Script to update manifests in '{actual_bucket_dir}' started.")
    print("---------------------------------------------------------")

    if not actual_bucket_dir.is_dir():
        print(f"Error: Bucket directory '{actual_bucket_dir}' not found.")
        exit(1)

    json_manifest_files = list(actual_bucket_dir.glob("*.json")) # Renamed variable
    apps_processed_for_readme = [] # Renamed variable
    any_change_made_in_run = False # Renamed variable

    if not json_manifest_files:
        print(f"No manifest files (.json) found in '{actual_bucket_dir}'.")
    else:
        for manifest_file_instance in json_manifest_files: # Renamed variable
            current_app_name = manifest_file_instance.stem # Renamed variable
            print(f"\nProcessing manifest: {current_app_name} (File: {manifest_file_instance.name})")
            print("---------------------------")
            
            # 1. Run 'scoop checkver -u'
            print(f"Running 'scoop checkver \"{current_app_name}\" -u'...")
            try:
                command_to_run = ["pwsh", "-NoProfile", "-Command", f"scoop checkver '{current_app_name}' -u"] # Renamed variable
                checkver_execution = subprocess.run( # Renamed variable
                    command_to_run, capture_output=True, text=True, check=False, encoding='utf-8', errors='replace'
                )
                if checkver_execution.returncode != 0:
                    print(f"  Warning: Command `{' '.join(command_to_run)}` finished with exit code {checkver_execution.returncode}.")
                    if checkver_execution.stdout and checkver_execution.stdout.strip(): print(f"    Scoop Checkver STDOUT:\n{checkver_execution.stdout.strip()}")
                    if checkver_execution.stderr and checkver_execution.stderr.strip(): print(f"    Scoop Checkver STDERR:\n{checkver_execution.stderr.strip()}")
                else:
                    print(f"  'scoop checkver -u' for '{current_app_name}' executed successfully (or no update was needed).")
                    if checkver_execution.stdout and checkver_execution.stdout.strip(): print(f"    Scoop Checkver Output:\n{checkver_execution.stdout.strip()}")
            except FileNotFoundError:
                print("  Error: 'pwsh' (PowerShell) not found. Cannot run 'scoop checkver'.")
            except Exception as e:
                print(f"  Warning: Error during execution of 'scoop checkver \"{current_app_name}\" -u': {e}")

            # 2. Read manifest content
            manifest_as_object = None # Renamed variable
            try:
                with open(manifest_file_instance, 'r', encoding='utf-8-sig') as f:
                    manifest_as_object = json.load(f)
            except Exception as e:
                print(f"  Error reading or parsing JSON manifest file '{manifest_file_instance}': {e}")
                any_change_made_in_run = True; continue

            # 3. Extract download URL and current hash
            url_to_download = None; hash_in_json = None # Renamed variables
            keys_for_hash_path = [] # Renamed variable

            if manifest_as_object.get("architecture", {}).get("64bit", {}).get("url"):
                url_to_download = manifest_as_object["architecture"]["64bit"]["url"]
                hash_in_json = manifest_as_object["architecture"]["64bit"].get("hash")
                keys_for_hash_path = ["architecture", "64bit", "hash"]
            elif manifest_as_object.get("url"):
                url_to_download = manifest_as_object["url"]
                hash_in_json = manifest_as_object.get("hash")
                keys_for_hash_path = ["hash"]
            
            if not url_to_download:
                print(f"  Warning: 'url' field not found or empty in manifest '{current_app_name}'. Skipping hash update.")
                apps_processed_for_readme.append(current_app_name)
                continue
            
            print(f"  Download URL found: {url_to_download}")
            print(f"  Current hash in manifest: {hash_in_json}")

            # 4. Download file
            temp_dir_for_downloads = repo_root_dir / "temp_scoop_downloads_python_v3" # Renamed variable
            temp_dir_for_downloads.mkdir(exist_ok=True)
            base_url_filename = os.path.basename(url_to_download.split('?')[0]) # Renamed
            sanitized_temp_filename = "".join(c if c.isalnum() or c in ['.', '-', '_'] else '_' for c in base_url_filename) # Renamed
            if not sanitized_temp_filename: sanitized_temp_filename = "downloaded_file_asset" # Renamed
            full_path_to_temp_file = temp_dir_for_downloads / f"{current_app_name}_{sanitized_temp_filename}.tmp" # Renamed

            was_download_successful = download_file_from_url(url_to_download, full_path_to_temp_file) # Renamed
            newly_found_hash = None # Renamed

            if was_download_successful:
                newly_found_hash = calculate_sha256_hash(full_path_to_temp_file)
                if newly_found_hash:
                    print(f"  New calculated hash for '{current_app_name}': {newly_found_hash}")
            
            if full_path_to_temp_file.exists():
                os.remove(full_path_to_temp_file)
            if temp_dir_for_downloads.exists() and not any(temp_dir_for_downloads.iterdir()):
                 temp_dir_for_downloads.rmdir()

            # 5. Compare and update manifest hash
            manifest_got_hash_update = False # Renamed
            if newly_found_hash and hash_in_json != newly_found_hash:
                print(f"  New hash ({newly_found_hash}) for '{current_app_name}' differs from current manifest hash ({hash_in_json}). Updating hash...")
                
                target_dict_for_hash = manifest_as_object # Renamed
                if keys_for_hash_path == ["architecture", "64bit", "hash"]:
                    if "architecture" in target_dict_for_hash and "64bit" in target_dict_for_hash["architecture"]:
                        target_dict_for_hash["architecture"]["64bit"]["hash"] = newly_found_hash
                        manifest_got_hash_update = True
                elif keys_for_hash_path == ["hash"]:
                    if "hash" in target_dict_for_hash or hash_in_json is not None :
                        target_dict_for_hash["hash"] = newly_found_hash
                        manifest_got_hash_update = True
                
                if not manifest_got_hash_update:
                     print(f"  Warning: Could not determine where to update hash in manifest '{current_app_name}'.")

            elif newly_found_hash:
                print(f"  Calculated hash for '{current_app_name}' is identical to the hash in the manifest. No hash update needed.")
            else:
                print(f"  Hash for '{current_app_name}' was not updated due to previous download/calculation errors.")
                any_change_made_in_run = True 

            if manifest_got_hash_update:
                 try:
                    with open(manifest_file_instance, 'w', encoding='utf-8') as f: # Save as UTF-8 (no BOM by default with 'w')
                        json.dump(manifest_as_object, f, indent=4, ensure_ascii=False)
                    print(f"  Manifest file '{current_app_name}' was successfully updated with the new hash.")
                    any_change_made_in_run = True
                 except Exception as e:
                    print(f"  Error saving updated manifest file '{current_app_name}': {e}")
                    any_change_made_in_run = True
            
            apps_processed_for_readme.append(current_app_name)
            print(f"Processing of manifest '{current_app_name}' finished.")
            print("---------------------------")

    # --- Update README.md ---
    # Determine bucket name and repo address for README
    repo_full_name_env = os.environ.get("GITHUB_REPOSITORY") # Renamed
    bucket_name_for_display_readme = "MyScoopBucket" # Default, Renamed
    repo_address_for_readme = "YourUsername/YourRepoName" # Default, Renamed

    if repo_full_name_env:
        repo_name_parts = repo_full_name_env.split('/') # Renamed
        if len(repo_name_parts) == 2:
            repo_address_for_readme = repo_full_name_env
            bucket_name_for_display_readme = repo_name_parts[1]
    else:
        try:
            git_remote_url_cmd_result = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=False, encoding='utf-8', errors='replace') # Renamed
            if git_remote_url_cmd_result.returncode == 0:
                git_remote_url_str = git_remote_url_cmd_result.stdout.strip() # Renamed
                # Regex to extract owner/repo from various git URL formats (HTTPS, SSH)
                regex_match_obj = re.search(r'github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?$', git_remote_url_str) # Renamed
                if regex_match_obj:
                    git_repo_owner, git_repo_actual_name = regex_match_obj.groups() # Renamed
                    repo_address_for_readme = f"{git_repo_owner}/{git_repo_actual_name}"
                    bucket_name_for_display_readme = git_repo_actual_name
                else:
                    print("Warning: Could not parse GitHub repository name from git remote URL for README.")
            else:
                print("Warning: 'git remote get-url origin' failed. Using default README info.")
        except Exception as e:
            print(f"Warning: Could not determine repository info from git for README: {e}. Using default README info.")

    readme_was_actually_changed = update_readme_content(actual_readme_file_path, apps_processed_for_readme, bucket_name_for_display_readme, repo_address_for_readme) # Renamed

    print("\n=========================================================")
    if any_change_made_in_run or readme_was_actually_changed :
        print("Update operation completed. Some files may have been modified or errors occurred.")
    else:
        print("Update operation for all manifests completed successfully (no changes were needed).")

if __name__ == "__main__":
    main()