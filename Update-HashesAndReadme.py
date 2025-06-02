# Update-HashesAndReadme.py
import os
import json
import hashlib
import subprocess
import requests
from pathlib import Path
import re

# --- Configuration ---
BUCKET_SUBDIRECTORY = "bucket" # Subdirectory containing app manifest JSON files
README_FILE_NAME = "README.md"   # Name of the README file in the repository root
# Placeholders in README.md to be replaced with the application list
APP_LIST_START_PLACEHOLDER = "{APP_LIST_START_PLACEHOLDER}"
APP_LIST_END_PLACEHOLDER = "{APP_LIST_END_PLACEHOLDER}"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
REQUEST_TIMEOUT_SECONDS = 300  # Timeout for downloading files

def calculate_sha256_hash(file_path: Path) -> str | None:
    """
    Calculates the SHA256 hash of a file.
    Args:
        file_path: Path to the file.
    Returns:
        Lowercase hexadecimal SHA256 hash string, or None if an error occurs.
    """
    sha256_hash_obj = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            # Read the file in chunks to handle large files efficiently
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash_obj.update(byte_block)
        return sha256_hash_obj.hexdigest().lower()
    except Exception as e:
        print(f"    Error calculating SHA256 for {file_path.name}: {e}")
        return None

def download_file_from_url(url: str, destination_path: Path) -> bool:
    """
    Downloads a file from a URL to a specified destination.
    Args:
        url: The URL to download from.
        destination_path: The path to save the downloaded file.
    Returns:
        True if download was successful, False otherwise.
    """
    print(f"    Downloading from: {url}")
    print(f"    Saving to temporary file: {destination_path.name}")
    try:
        headers = {"User-Agent": USER_AGENT}
        with requests.get(url, headers=headers, stream=True, timeout=REQUEST_TIMEOUT_SECONDS) as r:
            r.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
            with open(destination_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): # Write in chunks
                    f.write(chunk)
        print(f"    Download successful: {destination_path.name}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"    Error downloading file from '{url}': {e}")
        return False
    except Exception as e:
        print(f"    An unexpected error occurred during download from '{url}': {e}")
        return False

def update_readme_file(
    readme_file_path: Path,
    app_names_list: list[str],
    user_bucket_name: str,
    github_repo_address: str # Format: "owner/repo"
) -> bool:
    """
    Updates the README.md file with the list of applications.
    Creates a sample README if it doesn't exist.
    Args:
        readme_file_path: Path to the README.md file.
        app_names_list: A list of application names in the bucket.
        user_bucket_name: The name of the user's Scoop bucket for display.
        github_repo_address: The GitHub repository address (e.g., "owner/repo").
    Returns:
        True if the README was changed (created or updated), False otherwise.
    """
    print(f"\nAttempting to update README.md at: {readme_file_path}")
    repo_git_url = f"https://github.com/{github_repo_address}.git"
    readme_was_changed = False # Flag to track if README content actually changes

    # Default README content in Persian, using the defined placeholders
    # This content will be used if README.md does not exist.
    default_readme_text = f"""# مخزن Scoop شخصی {user_bucket_name}

به مخزن شخصی من برای نرم‌افزارهای Scoop خوش آمدید!
در اینجا مجموعه‌ای از مانیفست‌ها برای نصب آسان نرم‌افزارهای کاربردی، به خصوص ابزارهای مرتبط با شبکه و حریم خصوصی، قرار دارد. این مخزن به طور خودکار با استفاده از GitHub Actions به‌روزرسانی می‌شود.

## scoop

برای اضافه کردن این مخزن (Bucket) به Scoop خود و استفاده از نرم‌افزارهای آن، دستور زیر را در PowerShell اجرا کنید:

```powershell
scoop bucket add {user_bucket_name} {repo_git_url}
scoop install {user_bucket_name}/<program-name>
```

## Packages

```text
{APP_LIST_START_PLACEHOLDER}
(این لیست به طور خودکار توسط اسکریپت پایتون به‌روزرسانی خواهد شد. اگر این پیام را می‌بینید، یعنی اکشن هنوز اجرا نشده یا مشکلی در شناسایی پلیس‌هولدرها وجود داشته است.)
{APP_LIST_END_PLACEHOLDER}
```
---
می‌توانید وضعیت به‌روزرسانی‌های خودکار این مخزن را در صفحه Actions ما مشاهده کنید:
[صفحه وضعیت Actions](https://github.com/{github_repo_address}/actions)
"""

    if not readme_file_path.exists():
        print(f"README.md not found at '{readme_file_path}'. Creating a sample README.md.")
        try:
            readme_file_path.write_text(default_readme_text, encoding='utf-8')
            print(f"A sample README.md was created at '{readme_file_path}'.")
            readme_was_changed = True
        except Exception as e:
            print(f"Error creating sample README.md: {e}")
            return False # Stop if README creation fails

    try:
        current_readme_content = readme_file_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading README.md content from '{readme_file_path}': {e}")
        # If README was just created and reading fails, it's an issue.
        # If it existed and reading fails, also an issue.
        return False 

    # Prepare the list of application names for insertion into README
    app_list_for_readme = []
    if app_names_list:
        for app_name in sorted(app_names_list): # Sort app names alphabetically
            app_list_for_readme.append(f"- {app_name}") # Add a markdown list item prefix
    else:
        app_list_for_readme.append("(هنوز هیچ نرم‌افزاری به این مخزن اضافه نشده است.)")
    
    formatted_app_list_str = "\n".join(app_list_for_readme)

    # Find placeholders in the current README content
    start_index = current_readme_content.find(APP_LIST_START_PLACEHOLDER)
    end_index = current_readme_content.find(APP_LIST_END_PLACEHOLDER)

    if start_index != -1 and end_index != -1 and end_index > start_index:
        # Construct the new README content
        content_before_placeholder = current_readme_content[:start_index + len(APP_LIST_START_PLACEHOLDER)]
        content_after_placeholder = current_readme_content[end_index:]
        
        # Ensure proper newlines around the inserted list
        # Newline after start placeholder section
        if not content_before_placeholder.endswith(('\n', '\r\n')):
            content_before_placeholder += '\n'
        
        # Newline before end placeholder section (if list is not empty)
        list_to_insert = formatted_app_list_str
        if app_names_list and not list_to_insert.endswith(('\n', '\r\n')): # Only add newline if list has items
             list_to_insert += '\n'
        elif not app_names_list and not list_to_insert.endswith(('\n', '\r\n')): # For placeholder text
             list_to_insert += '\n'


        new_readme_content = f"{content_before_placeholder}{list_to_insert}{content_after_placeholder}"
        
        if new_readme_content != current_readme_content:
            try:
                readme_file_path.write_text(new_readme_content, encoding='utf-8')
                print("README.md was updated with the new list of applications.")
                if not readme_was_changed: readme_was_changed = True 
            except Exception as e:
                print(f"Error writing updated README.md: {e}")
        else:
            print("README.md application list is already up-to-date.")
    else:
        print(f"Warning: Placeholders '{APP_LIST_START_PLACEHOLDER}' and/or '{APP_LIST_END_PLACEHOLDER}' not found correctly in README.md.")
        print(f"         Ensure these exact strings exist and the start placeholder is before the end placeholder.")
    
    return readme_was_changed

def main():
    """
    Main function to orchestrate the update of hashes and README.
    """
    repo_root = Path(".").resolve() # Absolute path of the current working directory (repository root)
    bucket_dir = repo_root / BUCKET_SUBDIRECTORY
    readme_file = repo_root / README_FILE_NAME

    print(f"Python script started: Updating hashes and README in '{bucket_dir}'.")
    print("---------------------------------------------------------")

    if not bucket_dir.is_dir():
        print(f"Error: Bucket directory '{bucket_dir}' not found. Exiting.")
        exit(1) # Exit script with an error code

    manifest_files = list(bucket_dir.glob("*.json")) # Get all JSON files in the bucket directory
    processed_app_names = [] # List to store names of all processed apps for README
    any_manifest_updated_or_error_occurred = False # Flag for overall status

    if not manifest_files:
        print(f"No manifest files (.json) found in '{bucket_dir}'.")
    else:
        for manifest_file_path in manifest_files:
            app_name = manifest_file_path.stem # Get filename without extension (e.g., "app" from "app.json")
            print(f"\nProcessing manifest for hash update: {app_name} (File: {manifest_file_path.name})")
            print("---------------------------")
            
            manifest_data = None
            try:
                # Read manifest using utf-8-sig to handle potential BOM (Byte Order Mark)
                with open(manifest_file_path, 'r', encoding='utf-8-sig') as f:
                    manifest_data = json.load(f)
            except Exception as e:
                print(f"  Error reading or parsing JSON manifest file '{manifest_file_path}': {e}")
                processed_app_names.append(app_name) # Add to list for README even if processing fails
                any_manifest_updated_or_error_occurred = True # Flag an error occurred
                continue # Move to the next manifest file

            download_url = None
            current_hash_from_manifest = None
            hash_key_path_in_manifest = [] # To store the JSON path to the hash key

            # Check for URL and hash in common Scoop manifest structures
            # Structure 1: architecture -> 64bit -> url/hash
            if manifest_data.get("architecture", {}).get("64bit", {}).get("url"):
                download_url = manifest_data["architecture"]["64bit"]["url"]
                current_hash_from_manifest = manifest_data["architecture"]["64bit"].get("hash")
                hash_key_path_in_manifest = ["architecture", "64bit", "hash"]
            # Structure 2: Direct url/hash at the root
            elif manifest_data.get("url"):
                download_url = manifest_data["url"]
                current_hash_from_manifest = manifest_data.get("hash")
                hash_key_path_in_manifest = ["hash"]
            
            if not download_url:
                print(f"  Warning: 'url' field not found or empty in manifest '{app_name}'. Skipping hash update for this app.")
                processed_app_names.append(app_name)
                continue # Move to the next manifest
            
            print(f"  Download URL: {download_url}")
            print(f"  Current hash in manifest: {current_hash_from_manifest if current_hash_from_manifest else 'Not found'}")

            # Create a temporary directory for downloads
            temp_download_directory = repo_root / "temp_scoop_downloads_py_hash_readme"
            temp_download_directory.mkdir(exist_ok=True) # Create if not exists, do nothing if exists
            
            # Sanitize filename from URL for the temporary file
            url_filename_part = os.path.basename(download_url.split('?')[0]) # Get filename part before query parameters
            safe_temp_filename = "".join(c if c.isalnum() or c in ['.', '-', '_'] else '_' for c in url_filename_part)
            if not safe_temp_filename: safe_temp_filename = "downloaded_asset" # Fallback if sanitization results in empty string
            temp_file_full_path = temp_download_directory / f"{app_name}_{safe_temp_filename}.tmp"

            calculated_new_hash = None
            download_successful = download_file_from_url(download_url, temp_file_full_path)

            if download_successful:
                calculated_new_hash = calculate_sha256_hash(temp_file_full_path)
                if calculated_new_hash:
                    print(f"  New calculated hash: {calculated_new_hash}")
            
            # Clean up the temporary downloaded file
            if temp_file_full_path.exists():
                try:
                    os.remove(temp_file_full_path)
                except Exception as e_rm:
                    print(f"    Warning: Could not remove temporary file {temp_file_full_path}: {e_rm}")
            
            # Attempt to remove the temporary directory if it's empty
            if temp_download_directory.exists() and not any(temp_download_directory.iterdir()):
                try:
                    temp_download_directory.rmdir()
                except Exception as e_rmd:
                    print(f"    Warning: Could not remove temporary directory {temp_download_directory}: {e_rmd}")

            # Logic to update the hash in the manifest
            manifest_hash_field_updated_this_iteration = False
            if calculated_new_hash and (current_hash_from_manifest != calculated_new_hash or current_hash_from_manifest is None):
                print(f"  New hash ({calculated_new_hash}) differs from current manifest hash ({current_hash_from_manifest if current_hash_from_manifest else 'None'}) or current hash was missing. Updating manifest...")
                
                target_dict_for_hash_update = manifest_data # Start with the root of the manifest
                # Navigate to the correct dictionary level to update the hash
                if hash_key_path_in_manifest == ["architecture", "64bit", "hash"]:
                    if "architecture" in target_dict_for_hash_update and "64bit" in target_dict_for_hash_update["architecture"]:
                        target_dict_for_hash_update["architecture"]["64bit"]["hash"] = calculated_new_hash
                        manifest_hash_field_updated_this_iteration = True
                    else: # Should not happen if URL was found via this path
                        print(f"  Warning: Expected 'architecture.64bit' structure not found in '{app_name}' for hash update, though URL was found there.")
                elif hash_key_path_in_manifest == ["hash"]:
                    target_dict_for_hash_update["hash"] = calculated_new_hash
                    manifest_hash_field_updated_this_iteration = True
                
                if not manifest_hash_field_updated_this_iteration and hash_key_path_in_manifest: # If we expected to update but didn't
                     print(f"  Warning: Hash key path issue during update in manifest '{app_name}'. Hash not updated despite new hash calculation.")

            elif calculated_new_hash and current_hash_from_manifest == calculated_new_hash:
                print(f"  Hashes match. No hash update needed for '{app_name}'.")
            else: # calculated_new_hash is None (means download or hash calculation failed)
                print(f"  Hash for '{app_name}' not updated due to download/calculation errors.")
                any_manifest_updated_or_error_occurred = True # Flag that an error occurred

            if manifest_hash_field_updated_this_iteration:
                try:
                    # Write the updated manifest data back to the JSON file
                    with open(manifest_file_path, 'w', encoding='utf-8') as f:
                        json.dump(manifest_data, f, indent=4, ensure_ascii=False) # Pretty print with 4 spaces
                        f.write('\n') # Add a newline at the end, common practice for text files
                    print(f"  Manifest '{app_name}' updated successfully with new hash.")
                    any_manifest_updated_or_error_occurred = True # Flag that a file was changed
                except Exception as e:
                    print(f"  Error saving updated manifest '{app_name}': {e}")
                    any_manifest_updated_or_error_occurred = True # Flag that an error occurred
            
            processed_app_names.append(app_name) # Add to list for README update, regardless of hash update outcome
            print(f"Processing of manifest '{app_name}' finished.")
            print("---------------------------") # Separator for each app

    # --- Update README.md ---
    # Determine GitHub repository address (e.g., "owner/repo_name") for README links
    github_repo_env_var = os.environ.get("GITHUB_REPOSITORY") 
    # Bucket name to display in README 'scoop bucket add' command (user's preference)
    bucket_name_for_readme_display = "VpnClashFa"  
    # Default/fallback repository address for links if not found otherwise
    default_repo_for_readme_link = "vpnclashfa-backup/VpnClashFaScoopBucket" 
    
    actual_repo_for_readme_link = default_repo_for_readme_link # Initialize with fallback
    if github_repo_env_var: # Primarily use GITHUB_REPOSITORY if available (e.g., in GitHub Actions)
        actual_repo_for_readme_link = github_repo_env_var
    else:
        # Fallback: Try to get repo from git remote if GITHUB_REPOSITORY is not set (e.g. local run)
        try:
            # Run git command to get the origin URL
            origin_url_proc = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, check=False, # check=False to not raise error on non-zero exit
                encoding='utf-8', errors='replace' # Handle potential encoding issues
            )
            if origin_url_proc.returncode == 0 and origin_url_proc.stdout:
                origin_url = origin_url_proc.stdout.strip()
                # Regex to extract "owner/repo" from various GitHub URL formats (SSH, HTTPS)
                match = re.search(r'github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?$', origin_url)
                if match:
                    owner, repo_name = match.groups()
                    actual_repo_for_readme_link = f"{owner}/{repo_name}"
                else:
                    print("Warning: Could not parse GitHub repo name from git remote URL for README. Using hardcoded default.")
            else:
                print("Warning: 'git remote get-url origin' command failed or returned empty. Using hardcoded default README repo info.")
        except FileNotFoundError: # If git command is not found
            print("Warning: Git command not found. Cannot determine repo info from git. Using hardcoded defaults for README.")
        except Exception as e: # Catch any other unexpected errors
            print(f"Warning: Error determining repo info from git for README: {e}. Using hardcoded defaults.")

    readme_was_actually_modified = update_readme_file(
        readme_file,
        processed_app_names,
        bucket_name_for_readme_display,
        actual_repo_for_readme_link
    )

    print("\n=========================================================")
    if any_manifest_updated_or_error_occurred or readme_was_actually_modified:
        print("Update operation completed. Some files may have been modified or errors might have occurred.")
    else:
        print("Update operation for all manifests completed successfully (no changes were needed, and no errors occurred).")

if __name__ == "__main__":
    main()
