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
APP_LIST_START_PLACEHOLDER = "{APP_LIST_START_PLACEHOLDER}"
APP_LIST_END_PLACEHOLDER = "{APP_LIST_END_PLACEHOLDER}"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
REQUEST_TIMEOUT_SECONDS = 300

def calculate_sha256_hash(file_path: Path) -> str | None:
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
    print(f"    Downloading from: {url}")
    print(f"    Saving to temporary file: {destination_path.name}")
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

def update_readme_file(
    readme_file_path: Path,
    app_names_list: list[str],
    user_bucket_name: str,
    github_repo_address: str 
) -> bool:
    print(f"\nAttempting to update README.md at: {readme_file_path}")
    repo_git_url = f"https://github.com/{github_repo_address}.git"
    readme_was_changed = False 

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
            # After creating, read its content for further processing
            current_readme_content = default_readme_text
        except Exception as e:
            print(f"Error creating sample README.md: {e}")
            return False
    else:
        try:
            current_readme_content = readme_file_path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"Error reading README.md content from '{readme_file_path}': {e}")
            return False 

    app_list_for_md = []
    if app_names_list:
        for app_name in sorted(app_names_list): 
            app_list_for_md.append(f"{app_name}") # Keep the hyphen for markdown list format
    else:
        app_list_for_md.append("(هنوز هیچ نرم‌افزاری به این مخزن اضافه نشده است.)")
    
    formatted_app_list_str = "\n".join(app_list_for_md)

    start_index = current_readme_content.find(APP_LIST_START_PLACEHOLDER)
    end_index = current_readme_content.find(APP_LIST_END_PLACEHOLDER)

    new_readme_content = current_readme_content # Initialize with current content

    if start_index != -1 and end_index != -1 and end_index > start_index:
        # Content before the start placeholder string
        content_before = current_readme_content[:start_index]
        # Content after the end placeholder string
        content_after = current_readme_content[end_index + len(APP_LIST_END_PLACEHOLDER):]
        
        # Ensure there are appropriate newlines, especially if placeholders were on their own lines
        # or if the list should be separated.
        # This logic aims to place the list cleanly, removing the placeholder lines themselves.
        
        # Add a newline after content_before if it doesn't end with one and list is not empty
        if content_before and not content_before.endswith(('\n', '\r\n')):
            content_before += '\n'
        
        # Add a newline before content_after if it doesn't start with one and list is not empty
        if content_after and not content_after.startswith(('\n', '\r\n')):
             content_after = '\n' + content_after

        # If placeholders are within a ```text block, we need to be careful not to break it.
        # The new logic simply replaces the entire block from start_placeholder to end_placeholder.
        new_readme_content = f"{content_before}{formatted_app_list_str}{content_after}"
        
        # Normalize newlines for comparison and writing
        new_readme_content = new_readme_content.replace('\r\n', '\n')
        current_readme_content_normalized = current_readme_content.replace('\r\n', '\n')

        if new_readme_content != current_readme_content_normalized:
            try:
                readme_file_path.write_text(new_readme_content, encoding='utf-8', newline='\n')
                print("README.md was updated: Placeholders removed and list inserted.")
                if not readme_was_changed: readme_was_changed = True 
            except Exception as e:
                print(f"Error writing updated README.md: {e}")
        else:
            print("README.md content (app list) is already up-to-date and placeholders likely removed.")
    else:
        print(f"Warning: Placeholders '{APP_LIST_START_PLACEHOLDER}' and/or '{APP_LIST_END_PLACEHOLDER}' not found correctly in README.md.")
        print(f"         The list will not be updated. Please ensure these placeholders exist if this is the first run.")
    
    return readme_was_changed

def main():
    repo_root = Path(".").resolve() 
    bucket_dir = repo_root / BUCKET_SUBDIRECTORY 
    readme_file = repo_root / README_FILE_NAME   

    print(f"Python script 'Update-HashesAndReadme.py' started.")
    print(f"Processing manifests in bucket: '{bucket_dir}'.")
    print(f"README file expected at: '{readme_file}'.")
    print("---------------------------------------------------------")

    if not bucket_dir.is_dir():
        print(f"Error: Bucket directory '{bucket_dir}' not found. Exiting.")
        exit(1)

    manifest_files = list(bucket_dir.glob("*.json")) 
    processed_app_names = [] 
    any_manifest_updated_or_error_occurred = False 

    if not manifest_files:
        print(f"No manifest files (.json) found in '{bucket_dir}'.")
    else:
        for manifest_file_path in manifest_files:
            app_name = manifest_file_path.stem 
            print(f"\nProcessing manifest for hash update: {app_name} (File: {manifest_file_path.name})")
            # ... (بقیه منطق محاسبه و به‌روزرسانی هش بدون تغییر باقی می‌ماند) ...
            # This is the existing hash update logic you confirmed was working.
            # It should remain the same.
            # For brevity, I'm not repeating the full hash logic here, assume it's the same as python_script_v3_full
            manifest_data = None
            try:
                with open(manifest_file_path, 'r+', encoding='utf-8-sig') as f: # Open in r+ for reading and writing
                    manifest_data = json.load(f)
            
                    download_url = None
                    current_hash_from_manifest = None
                    hash_key_path_in_manifest = [] 

                    if manifest_data.get("architecture", {}).get("64bit", {}).get("url"):
                        download_url = manifest_data["architecture"]["64bit"]["url"]
                        current_hash_from_manifest = manifest_data["architecture"]["64bit"].get("hash")
                        hash_key_path_in_manifest = ["architecture", "64bit", "hash"]
                    elif manifest_data.get("url"):
                        download_url = manifest_data["url"]
                        current_hash_from_manifest = manifest_data.get("hash")
                        hash_key_path_in_manifest = ["hash"]
                    
                    if not download_url:
                        print(f"  Warning: 'url' field not found in manifest '{app_name}'. Skipping hash calculation.")
                        processed_app_names.append(app_name)
                        continue 
                    
                    if not current_hash_from_manifest or current_hash_from_manifest == "":
                        print(f"  Hash is missing or empty for {app_name}. Calculating new hash...")
                        
                        temp_download_directory = repo_root / "temp_scoop_downloads_py_hash_readme" 
                        temp_download_directory.mkdir(exist_ok=True) 
                        
                        url_filename_part = os.path.basename(download_url.split('?')[0]) 
                        safe_temp_filename = "".join(c if c.isalnum() or c in ['.', '-', '_'] else '_' for c in url_filename_part)
                        if not safe_temp_filename: safe_temp_filename = "downloaded_asset_for_hash" 
                        temp_file_full_path = temp_download_directory / f"{app_name}_{safe_temp_filename}.tmp"

                        calculated_new_hash = None
                        download_successful = download_file_from_url(download_url, temp_file_full_path)

                        if download_successful:
                            calculated_new_hash = calculate_sha256_hash(temp_file_full_path)
                        
                        if temp_file_full_path.exists():
                            try: os.remove(temp_file_full_path)
                            except Exception as e_rm: print(f"    Warning: Could not remove temp file {temp_file_full_path}: {e_rm}")
                        
                        if calculated_new_hash:
                            print(f"  New calculated hash: {calculated_new_hash}")
                            if hash_key_path_in_manifest == ["architecture", "64bit", "hash"]:
                                manifest_data["architecture"]["64bit"]["hash"] = calculated_new_hash
                            elif hash_key_path_in_manifest == ["hash"]:
                                manifest_data["hash"] = calculated_new_hash
                            
                            f.seek(0)
                            json.dump(manifest_data, f, indent=4, ensure_ascii=False) 
                            f.write('\n') 
                            f.truncate() 
                            print(f"  Manifest for {app_name} updated with new hash.")
                            any_manifest_updated_or_error_occurred = True
                        else:
                            print(f"  Failed to calculate new hash for {app_name}. Manifest not updated with new hash.")
                            any_manifest_updated_or_error_occurred = True
                    else:
                        print(f"  Hash already present for {app_name}: {current_hash_from_manifest}")

            except Exception as e:
                print(f"  Error processing manifest file '{manifest_file_path.name}': {e}")
                any_manifest_updated_or_error_occurred = True 
            
            processed_app_names.append(app_name) 
            print(f"Processing of manifest '{app_name}' finished.")
            print("---------------------------") 
    
    temp_dir_to_clean = repo_root / "temp_scoop_downloads_py_hash_readme"
    if temp_dir_to_clean.exists() and not any(temp_dir_to_clean.iterdir()):
        try: temp_dir_to_clean.rmdir()
        except Exception as e_rmd: print(f"    Warning: Could not remove temp hash dir {temp_dir_to_clean}: {e_rmd}")

    github_repo_env_var = os.environ.get("GITHUB_REPOSITORY") 
    bucket_name_for_readme_display = "VpnClashFa"  
    default_repo_for_readme_link = "vpnclashfa-backup/VpnClashFaScoopBucket" 
    
    actual_repo_for_readme_link = default_repo_for_readme_link 
    if github_repo_env_var: 
        actual_repo_for_readme_link = github_repo_env_var
    else:
        try:
            origin_url_proc = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, check=False, 
                encoding='utf-8', errors='replace' 
            )
            if origin_url_proc.returncode == 0 and origin_url_proc.stdout:
                origin_url = origin_url_proc.stdout.strip()
                match = re.search(r'github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?$', origin_url)
                if match:
                    owner, repo_name = match.groups()
                    actual_repo_for_readme_link = f"{owner}/{repo_name}"
                else:
                    print("Warning: Could not parse GitHub repo name from git remote URL for README.")
            else:
                print("Warning: 'git remote get-url origin' command failed or returned empty.")
        except FileNotFoundError: 
            print("Warning: Git command not found. Cannot determine repo info from git.")
        except Exception as e: 
            print(f"Warning: Error determining repo info from git for README: {e}.")

    readme_was_actually_modified = update_readme_file(
        readme_file, 
        list(set(processed_app_names)), 
        bucket_name_for_readme_display,
        actual_repo_for_readme_link
    )

    print("\n=========================================================")
    if any_manifest_updated_or_error_occurred or readme_was_actually_modified:
        print("Update operation (hashes/README) completed. Some files may have been modified or errors might have occurred.")
    else:
        print("Update operation (hashes/README) completed successfully (no changes were needed, and no errors occurred).")

if __name__ == "__main__":
    main()
