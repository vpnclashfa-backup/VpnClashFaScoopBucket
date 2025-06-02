# Update-HashesAndReadme.py
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
# Corrected Placeholders to match the literal strings in the README template
APP_LIST_START_PLACEHOLDER = "{APP_LIST_START_PLACEHOLDER}"
APP_LIST_END_PLACEHOLDER = "{APP_LIST_END_PLACEHOLDER}"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
REQUEST_TIMEOUT_SECONDS = 300

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

def update_readme_file(
    readme_file_path: Path,
    app_names_list: list[str],
    user_bucket_name: str,
    github_repo_address: str
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
    readme_was_changed = False

    if not readme_file_path.exists():
        print(f"README.md not found at '{readme_file_path}'. Creating a sample README.md.")
        # Default README content in Persian, using the corrected placeholders
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
        return False # Stop if README reading fails

    app_list_for_readme = []
    if app_names_list:
        for app_name in sorted(app_names_list): # Sort app names alphabetically
            app_list_for_readme.append(app_name)
    else:
        app_list_for_readme.append("(هنوز هیچ نرم‌افزاری به این مخزن اضافه نشده است.)")
    
    formatted_app_list = "\n".join(app_list_for_readme)

    # Use the string constants for placeholders
    start_placeholder_str = APP_LIST_START_PLACEHOLDER
    end_placeholder_str = APP_LIST_END_PLACEHOLDER

    if current_readme_content: # Ensure content was read
        start_index = current_readme_content.find(start_placeholder_str)
        end_index = current_readme_content.find(end_placeholder_str)

        if start_index != -1 and end_index != -1 and end_index > start_index:
            # Construct the new content carefully to preserve formatting
            content_before_placeholder_section = current_readme_content[:start_index + len(start_placeholder_str)]
            
            # Ensure there's a newline after the start placeholder segment if not already present
            if not content_before_placeholder_section.endswith(('\n', '\r\n')):
                content_before_placeholder_section += '\n'
            
            content_after_placeholder_section = current_readme_content[end_index:] # This includes the end placeholder itself

            # Ensure the list to insert ends with a newline before appending the 'after' part
            list_to_insert = formatted_app_list
            if not list_to_insert.endswith(('\n', '\r\n')):
                list_to_insert += '\n'
            
            new_readme_content = f"{content_before_placeholder_section}{list_to_insert}{content_after_placeholder_section}"
            
            if new_readme_content != current_readme_content:
                try:
                    readme_file_path.write_text(new_readme_content, encoding='utf-8')
                    print("README.md was updated with the new list of applications.")
                    if not readme_was_changed: readme_was_changed = True # Mark as changed if not already (e.g., if it was just created)
                except Exception as e:
                    print(f"Error writing updated README.md: {e}")
            else:
                print("README.md application list is already up-to-date.")
        else:
            print(f"Warning: Placeholders '{start_placeholder_str}' and/or '{end_placeholder_str}' not found in README.md or in incorrect order.")
            print(f"         Please ensure these exact strings exist in your README template and the start placeholder comes before the end placeholder.")
    else:
        # This case should ideally not be reached if README creation/reading was successful
        print(f"Warning: README.md content is not available for placeholder processing (this should not happen if reading was successful).")
    
    return readme_was_changed

def main():
    """
    Main function to orchestrate the update of hashes and README.
    """
    repo_root = Path(".").resolve() # Get the absolute path of the current working directory
    bucket_dir = repo_root / BUCKET_SUBDIRECTORY
    readme_file = repo_root / README_FILE_NAME

    print(f"Python script started: Updating hashes and README in '{bucket_dir}'.")
    print("---------------------------------------------------------")

    if not bucket_dir.is_dir():
        print(f"Error: Bucket directory '{bucket_dir}' not found. Exiting.")
        exit(1)

    manifest_files = list(bucket_dir.glob("*.json"))
    processed_app_names = []
    any_manifest_updated_or_error_occurred = False # Initialize flag for overall status

    if not manifest_files:
        print(f"No manifest files (.json) found in '{bucket_dir}'.")
    else:
        for manifest_file_path in manifest_files:
            app_name = manifest_file_path.stem # Get filename without extension
            print(f"\nProcessing manifest for hash update: {app_name} (File: {manifest_file_path.name})")
            print("---------------------------")
            
            manifest_data = None
            try:
                # Use utf-8-sig to handle potential BOM (Byte Order Mark)
                with open(manifest_file_path, 'r', encoding='utf-8-sig') as f:
                    manifest_data = json.load(f)
            except Exception as e:
                print(f"  Error reading or parsing JSON manifest file '{manifest_file_path}': {e}")
                processed_app_names.append(app_name) # Add to list for README even if processing fails here
                any_manifest_updated_or_error_occurred = True # Flag that an error occurred
                continue # Move to the next manifest file

            download_url = None
            current_hash = None
            hash_path_keys = [] # To store the path to the hash key in the manifest dict

            # Check for URL and hash in common Scoop manifest structures
            if manifest_data.get("architecture", {}).get("64bit", {}).get("url"):
                download_url = manifest_data["architecture"]["64bit"]["url"]
                current_hash = manifest_data["architecture"]["64bit"].get("hash")
                hash_path_keys = ["architecture", "64bit", "hash"]
            elif manifest_data.get("url"):
                download_url = manifest_data["url"]
                current_hash = manifest_data.get("hash")
                hash_path_keys = ["hash"]
            
            if not download_url:
                print(f"  Warning: 'url' field not found or empty in manifest '{app_name}'. Skipping hash update for this app.")
                processed_app_names.append(app_name)
                continue
            
            print(f"  Download URL: {download_url}")
            print(f"  Current hash: {current_hash if current_hash else 'Not found'}")

            # Create a temporary directory for downloads if it doesn't exist
            temp_dl_dir = repo_root / "temp_scoop_downloads_py_hash_readme"
            temp_dl_dir.mkdir(exist_ok=True)
            
            # Sanitize filename from URL for the temporary file
            url_filename_part = os.path.basename(download_url.split('?')[0]) # Get filename before query params
            safe_tmp_filename = "".join(c if c.isalnum() or c in ['.', '-', '_'] else '_' for c in url_filename_part)
            if not safe_tmp_filename: safe_tmp_filename = "downloaded_asset" # Fallback if sanitization results in empty string
            tmp_file_location = temp_dl_dir / f"{app_name}_{safe_tmp_filename}.tmp"

            new_hash = None
            download_ok = download_file_from_url(download_url, tmp_file_location)

            if download_ok:
                new_hash = calculate_sha256_hash(tmp_file_location)
                if new_hash:
                    print(f"  New calculated hash: {new_hash}")
            
            # Clean up the temporary downloaded file
            if tmp_file_location.exists():
                try:
                    os.remove(tmp_file_location)
                except Exception as e_rm:
                    print(f"    Warning: Could not remove temporary file {tmp_file_location}: {e_rm}")
            
            # Attempt to remove the temporary directory if it's empty
            if temp_dl_dir.exists() and not any(temp_dl_dir.iterdir()):
                try:
                    temp_dl_dir.rmdir()
                except Exception as e_rmd:
                    print(f"    Warning: Could not remove temporary directory {temp_dl_dir}: {e_rmd}")

            manifest_hash_was_updated_this_iteration = False
            if new_hash and (current_hash != new_hash or current_hash is None): # Update if different or if old hash was missing
                print(f"  New hash ({new_hash}) differs from current ({current_hash if current_hash else 'None'}) or current hash was missing. Updating manifest...")
                
                target_dict_for_hash = manifest_data
                # Navigate to the correct dictionary level to update the hash
                if hash_path_keys == ["architecture", "64bit", "hash"]:
                    if "architecture" in target_dict_for_hash and "64bit" in target_dict_for_hash["architecture"]:
                        target_dict_for_hash["architecture"]["64bit"]["hash"] = new_hash
                        manifest_hash_was_updated_this_iteration = True
                    else:
                        print(f"  Warning: Expected 'architecture.64bit' structure not found in '{app_name}' for hash update.")
                elif hash_path_keys == ["hash"]:
                    target_dict_for_hash["hash"] = new_hash
                    manifest_hash_was_updated_this_iteration = True
                
                if not manifest_hash_was_updated_this_iteration and hash_path_keys:
                     print(f"  Warning: Hash key path issue in manifest '{app_name}'. Hash not updated despite new hash calculation.")

            elif new_hash and current_hash == new_hash: # Hashes match
                print(f"  Hashes match. No hash update needed for '{app_name}'.")
            else: # new_hash is None (download or hash calculation failed)
                print(f"  Hash for '{app_name}' not updated due to download/calculation errors.")
                any_manifest_updated_or_error_occurred = True # Flag that an error occurred

            if manifest_hash_was_updated_this_iteration:
                try:
                    # Write the updated manifest back to the file
                    # Use indent for readability and ensure_ascii=False for non-ASCII chars
                    with open(manifest_file_path, 'w', encoding='utf-8') as f:
                        json.dump(manifest_data, f, indent=4, ensure_ascii=False)
                        f.write('\n') # Add a newline at the end, common practice
                    print(f"  Manifest '{app_name}' updated successfully with new hash.")
                    any_manifest_updated_or_error_occurred = True # Flag that a change was made
                except Exception as e:
                    print(f"  Error saving updated manifest '{app_name}': {e}")
                    any_manifest_updated_or_error_occurred = True # Flag that an error occurred
            
            processed_app_names.append(app_name) # Add to list for README update
            print(f"Processing of manifest '{app_name}' finished.")
            print("---------------------------")

    # --- Update README.md ---
    github_repo_env = os.environ.get("GITHUB_REPOSITORY") # e.g., "owner/repo"
    # Bucket name to display in README 'scoop bucket add' command
    bucket_name_for_readme_display = "VpnClashFa" # As per user's hardcoded value
    # Actual repository address for links, try to derive it, fallback to user's specific repo
    default_repo_for_readme_link = "vpnclashfa-backup/VpnClashFaScoopBucket" # User's hardcoded fallback
    
    actual_repo_for_readme_link = default_repo_for_readme_link # Initialize with fallback
    if github_repo_env:
        actual_repo_for_readme_link = github_repo_env
    else:
        # Try to get repo from git remote if GITHUB_REPOSITORY is not set (e.g. local run)
        try:
            # Run git command to get the origin URL
            origin_url_proc = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, check=False, encoding='utf-8', errors='replace'
            )
            if origin_url_proc.returncode == 0:
                origin_url = origin_url_proc.stdout.strip()
                # Regex to extract "owner/repo" from various GitHub URL formats
                match = re.search(r'github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?$', origin_url)
                if match:
                    owner, repo_name = match.groups()
                    actual_repo_for_readme_link = f"{owner}/{repo_name}"
                else:
                    print("Warning: Could not parse GitHub repo name from git remote URL for README. Using hardcoded default.")
            else:
                print("Warning: 'git remote get-url origin' command failed. Using hardcoded default README repo info.")
        except FileNotFoundError:
            print("Warning: Git command not found. Cannot determine repo info from git. Using hardcoded defaults for README.")
        except Exception as e:
            print(f"Warning: Error determining repo info from git for README: {e}. Using hardcoded defaults.")

    readme_was_modified = update_readme_file(
        readme_file,
        processed_app_names,
        bucket_name_for_readme_display,
        actual_repo_for_readme_link
    )

    print("\n=========================================================")
    if any_manifest_updated_or_error_occurred or readme_was_modified:
        print("Update operation completed. Some files may have been modified or errors might have occurred.")
    else:
        print("Update operation for all manifests completed successfully (no changes were needed, and no errors occurred).")

if __name__ == "__main__":
    main()
