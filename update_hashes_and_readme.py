# update_hashes_and_readme.py
import os
import json
import hashlib
import subprocess # For git commands if run locally for README info
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

def update_readme_file_content(
    readme_file_path: Path,
    app_names_list: list[str],
    user_bucket_name_for_display: str, # e.g., VpnClashFa
    github_repo_full_address_for_link: str # e.g., vpnclashfa-backup/VpnClashFaScoopBucket
) -> bool:
    print(f"\nAttempting to update README.md at: {readme_file_path}")
    repo_git_url_for_command = f"[https://github.com/](https://github.com/){github_repo_full_address_for_link}.git" # Corrected variable name
    readme_was_actually_modified_flag = False # Renamed variable

    # Default README content with correct placeholders and structure
    default_readme_text_content = f"""# مخزن Scoop شخصی {user_bucket_name_for_display}

به مخزن شخصی من برای نرم‌افزارهای Scoop خوش آمدید!
در اینجا مجموعه‌ای از مانیفست‌ها برای نصب آسان نرم‌افزارهای کاربردی، به خصوص ابزارهای مرتبط با شبکه و حریم خصوصی، قرار دارد. این مخزن به طور خودکار با استفاده از GitHub Actions به‌روزرسانی می‌شود.

## scoop

برای اضافه کردن این مخزن (Bucket) به Scoop خود و استفاده از نرم‌افزارهای آن، دستور زیر را در PowerShell اجرا کنید:

```powershell
scoop bucket add {user_bucket_name_for_display} {repo_git_url_for_command}
scoop install {user_bucket_name_for_display}/<program-name>
```

پس از اضافه کردن مخزن، برای نصب یک نرم‌افزار از لیست زیر، از دستور `scoop install <نام_نرم‌افزار>` استفاده کنید. به عنوان مثال:

```powershell
scoop install {user_bucket_name_for_display}/clash-verge-rev
```

می‌توانید وضعیت و تاریخچه به‌روزرسانی‌های خودکار این مخزن را در صفحه Actions ما مشاهده کنید:
[صفحه وضعیت Actions](https://github.com/{github_repo_full_address_for_link}/actions)

## Packages
```text
{APP_LIST_START_PLACEHOLDER}
(این لیست به طور خودکار توسط اسکریپت پایتون به‌روزرسانی خواهد شد. اگر این پیام را می‌بینید، یعنی اکشن هنوز اجرا نشده یا مشکلی در شناسایی پلیس‌هولدرها وجود داشته است.)
{APP_LIST_END_PLACEHOLDER}
```
---

اگر پیشنهاد یا مشکلی در مورد این مخزن دارید، لطفاً یک Issue جدید در صفحه گیت‌هاب این ریپازیتوری باز کنید.
"""
    if not readme_file_path.exists():
        print(f"README.md not found at '{readme_file_path}'. Creating a sample README.md.")
        try:
            readme_file_path.write_text(default_readme_text_content, encoding='utf-8')
            print(f"A sample README.md was created at '{readme_file_path}'.")
            readme_was_actually_modified_flag = True 
        except Exception as e:
            print(f"Error creating sample README.md: {e}")
            return False

    try:
        current_readme_text_content = readme_file_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading README.md content from '{readme_file_path}': {e}")
        return False

    app_list_for_insertion = []
    if app_names_list:
        for app_name_item_entry in sorted(app_names_list):
            app_list_for_insertion.append(app_name_item_entry)
    else:
        app_list_for_insertion.append("(هنوز هیچ نرم‌افزاری به این مخزن اضافه نشده است.)")
    
    formatted_app_list_string = "\n".join(app_list_for_insertion)

    start_placeholder = APP_LIST_START_PLACEHOLDER
    end_placeholder = APP_LIST_END_PLACEHOLDER

    if current_readme_text_content:
        start_index_val = current_readme_text_content.find(start_placeholder)
        end_index_val = current_readme_text_content.find(end_placeholder)

        if start_index_val != -1 and end_index_val != -1 and end_index_val > start_index_val:
            text_before_app_list = current_readme_text_content[:start_index_val + len(start_placeholder)]
            if not text_before_app_list.endswith(('\n', '\r\n')):
                text_before_app_list += '\n'
            
            text_after_app_list = current_readme_text_content[end_index_val:]
            
            final_app_list_to_insert = formatted_app_list_string
            if not final_app_list_to_insert.endswith(('\n', '\r\n')):
                final_app_list_to_insert += '\n'
                
            new_complete_readme_text = f"{text_before_app_list}{final_app_list_to_insert}{text_after_app_list}"
            
            if new_complete_readme_text != current_readme_text_content:
                try:
                    readme_file_path.write_text(new_complete_readme_text, encoding='utf-8')
                    print("README.md was updated with the new list of applications.")
                    if not readme_was_actually_modified_flag: readme_was_actually_modified_flag = True
                except Exception as e:
                    print(f"Error writing updated README.md: {e}")
            else:
                print("README.md application list is already up-to-date.")
        else:
            # This case is important: if placeholders are not in the README.md created by this script
            # it means there's a logic error in how the default_readme_text_content is defined above.
            print(f"Warning: Placeholders '{start_placeholder}' and/or '{end_placeholder}' not found in README.md at '{readme_file_path}'.")
            print("The application list was not updated. Please ensure the README.md file (or its auto-generation logic) includes these exact placeholders.")
    else:
         print(f"Warning: README.md content at '{readme_file_path}' is not available for placeholder processing (it might be empty or unreadable).")
    
    return readme_was_actually_modified_flag

def main():
    repo_root = Path(".").resolve() 
    bucket_dir = repo_root / BUCKET_SUBDIRECTORY 
    readme_file = repo_root / README_FILE_NAME 

    print(f"Script to update manifest hashes and README in '{bucket_dir}' started.")
    print("---------------------------------------------------------")

    if not bucket_dir.is_dir():
        print(f"Error: Bucket directory '{bucket_dir}' not found.")
        exit(1)

    manifest_files = list(bucket_dir.glob("*.json")) 
    processed_app_names = [] 
    any_manifest_updated = False 

    if not manifest_files:
        print(f"No manifest files (.json) found in '{bucket_dir}'.")
    else:
        for manifest_file_path in manifest_files: 
            app_name = manifest_file_path.stem 
            print(f"\nProcessing manifest for hash update: {app_name} (File: {manifest_file_path.name})")
            print("---------------------------")
            
            manifest_content_obj = None
            try:
                with open(manifest_file_path, 'r', encoding='utf-8-sig') as f: 
                    manifest_content_obj = json.load(f)
            except Exception as e:
                print(f"  Error reading or parsing JSON manifest file '{manifest_file_path}': {e}")
                any_manifest_updated = True # Mark as potential issue
                processed_app_names.append(app_name) # Add to list for README even if hash update fails
                continue

            download_url_from_file = None; current_hash_from_file = None 
            path_to_hash_key = [] 

            if manifest_content_obj.get("architecture", {}).get("64bit", {}).get("url"):
                download_url_from_file = manifest_content_obj["architecture"]["64bit"]["url"]
                current_hash_from_file = manifest_content_obj["architecture"]["64bit"].get("hash")
                path_to_hash_key = ["architecture", "64bit", "hash"]
            elif manifest_content_obj.get("url"):
                download_url_from_file = manifest_content_obj["url"]
                current_hash_from_file = manifest_content_obj.get("hash")
                path_to_hash_key = ["hash"]
            
            if not download_url_from_file:
                print(f"  Warning: 'url' field not found or empty in manifest '{app_name}'. Skipping hash update.")
                processed_app_names.append(app_name)
                continue
            
            print(f"  Download URL found: {download_url_from_file}")
            print(f"  Current hash in manifest: {current_hash_from_file}")

            temp_download_storage_dir = repo_root / "temp_scoop_downloads_py_hash_only" 
            temp_download_storage_dir.mkdir(exist_ok=True)
            filename_part_from_url = os.path.basename(download_url_from_file.split('?')[0]) 
            safe_temp_filename_part = "".join(c if c.isalnum() or c in ['.', '-', '_'] else '_' for c in filename_part_from_url) 
            if not safe_temp_filename_part: safe_temp_filename_part = "scoop_downloaded_file" 
            full_temp_file_path = temp_download_storage_dir / f"{app_name}_{safe_temp_filename_part}.tmp" 

            was_download_ok = download_file_from_url(download_url_from_file, full_temp_file_path) 
            newly_calculated_hash_str = None 

            if was_download_ok:
                newly_calculated_hash_str = calculate_sha256_hash(full_temp_file_path)
                if newly_calculated_hash_str:
                    print(f"  New calculated hash for '{app_name}': {newly_calculated_hash_str}")
            
            if full_temp_file_path.exists():
                try: os.remove(full_temp_file_path)
                except Exception as e_rm: print(f"    Warning: Could not remove temporary file {full_temp_file_path}: {e_rm}")
            
            if temp_download_storage_dir.exists() and not any(temp_download_storage_dir.iterdir()):
                 try: temp_download_storage_dir.rmdir()
                 except Exception as e_rmd: print(f"    Warning: Could not remove temporary directory {temp_download_storage_dir}: {e_rmd}")

            manifest_hash_was_updated = False 
            if newly_calculated_hash_str and current_hash_from_file != newly_calculated_hash_str:
                print(f"  New hash ({newly_calculated_hash_str}) for '{app_name}' differs from current manifest hash ({current_hash_from_file}). Updating hash...")
                
                target_json_dict = manifest_content_obj 
                if path_to_hash_key == ["architecture", "64bit", "hash"]:
                    if "architecture" in target_json_dict and "64bit" in target_json_dict["architecture"]:
                        target_json_dict["architecture"]["64bit"]["hash"] = newly_calculated_hash_str
                        manifest_hash_was_updated = True
                elif path_to_hash_key == ["hash"]:
                    if "hash" in target_json_dict or current_hash_from_file is not None :
                        target_json_dict["hash"] = newly_calculated_hash_str
                        manifest_hash_was_updated = True
                
                if not manifest_hash_was_updated and (path_to_hash_key == ["architecture", "64bit", "hash"] or path_to_hash_key == ["hash"]):
                     print(f"  Warning: Hash key structure issue in manifest '{app_name}'. Hash not updated.")

            elif newly_calculated_hash_str:
                print(f"  Calculated hash for '{app_name}' is identical to the hash in the manifest. No hash update needed.")
            else:
                print(f"  Hash for '{app_name}' was not updated due to previous download/calculation errors.")
                any_manifest_updated = True 

            if manifest_hash_was_updated:
                 try:
                    with open(manifest_file_path, 'w', encoding='utf-8') as f: 
                        json.dump(manifest_content_obj, f, indent=4, ensure_ascii=False)
                    print(f"  Manifest file '{app_name}' was successfully updated with the new hash.")
                    any_manifest_updated = True
                 except Exception as e:
                    print(f"  Error saving updated manifest file '{app_name}': {e}")
                    any_manifest_updated = True
            
            processed_app_names.append(app_name)
            print(f"Processing of manifest '{app_name}' finished.")
            print("---------------------------")

    # --- Update README.md ---
    github_repo_env = os.environ.get("GITHUB_REPOSITORY") 
    bucket_name_for_readme = "VpnClashFa" 
    repo_address_for_readme = "vpnclashfa-backup/VpnClashFaScoopBucket" 

    if github_repo_env: 
        repo_parts = github_repo_env.split('/') 
        if len(repo_parts) == 2:
            repo_address_for_readme = github_repo_env
    else: 
        try:
            origin_url_proc = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=False, encoding='utf-8', errors='replace') 
            if origin_url_proc.returncode == 0:
                origin_url = origin_url_proc.stdout.strip() 
                match = re.search(r'github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?$', origin_url) 
                if match:
                    owner, repo = match.groups() 
                    repo_address_for_readme = f"{owner}/{repo}"
                else:
                    print("Warning: Could not parse GitHub repository name from git remote URL for README. Using defaults.")
            else:
                print("Warning: 'git remote get-url origin' failed. Using default README info.")
        except Exception as e:
            print(f"Warning: Could not determine repository info from git for README: {e}. Using default README info.")

    readme_changed_by_script = update_readme_file( 
        readme_file, 
        processed_app_names, 
        bucket_name_for_readme, 
        repo_address_for_readme
    )

    print("\n=========================================================")
    if any_manifest_updated or readme_changed_by_script :
        print("Update operation completed. Some files may have been modified or errors occurred.")
    else:
        print("Update operation for all manifests completed successfully (no changes were needed).")

if __name__ == "__main__":
    main()
