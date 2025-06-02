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
    user_bucket_name: str, # e.g., VpnClashFa
    github_repo_full_address: str # e.g., vpnclashfa-backup/VpnClashFaScoopBucket
) -> bool:
    print(f"\nAttempting to update README.md at: {readme_file_path}")
    repo_git_url = f"https://github.com/{github_repo_full_address}.git"
    readme_content_was_changed = False

    if not readme_file_path.exists():
        print(f"Warning: README.md not found at '{readme_file_path}'. Creating a sample README.md.")
        default_readme_text = f"""# مخزن Scoop شخصی {user_bucket_name}

به مخزن شخصی من برای نرم‌افزارهای Scoop خوش آمدید!
در اینجا مجموعه‌ای از مانیفست‌ها برای نصب آسان نرم‌افزارهای کاربردی، به خصوص ابزارهای مرتبط با شبکه و حریم خصوصی، قرار دارد. این مخزن به طور خودکار با استفاده از GitHub Actions به‌روزرسانی می‌شود.

## scoop

برای اضافه کردن این مخزن (Bucket) به Scoop خود و استفاده از نرم‌افزارهای آن، دستور زیر را در PowerShell اجرا کنید:

```powershell
scoop bucket add {user_bucket_name} {repo_git_url}
scoop install {user_bucket_name}/<program-name>
```

پس از اضافه کردن مخزن، برای نصب یک نرم‌افزار از لیست زیر، از دستور `scoop install <نام_نرم‌افزار>` استفاده کنید. به عنوان مثال:

```powershell
scoop install {user_bucket_name}/clash-verge-rev
```

می‌توانید وضعیت و تاریخچه به‌روزرسانی‌های خودکار این مخزن را در صفحه Actions ما مشاهده کنید:
[صفحه وضعیت Actions](https://github.com/{github_repo_full_address}/actions)

## Packages
```text
{APP_LIST_START_PLACEHOLDER}
(این لیست به طور خودکار توسط اسکریپت پایتون به‌روزرسانی خواهد شد. اگر این پیام را می‌بینید، یعنی اکشن هنوز اجرا نشده یا مشکلی در شناسایی پلیس‌هولدرها وجود داشته است.)
{APP_LIST_END_PLACEHOLDER}
```
---

اگر پیشنهاد یا مشکلی در مورد این مخزن دارید، لطفاً یک Issue جدید در صفحه گیت‌هاب این ریپازیتوری باز کنید.
"""
        try:
            readme_file_path.write_text(default_readme_text, encoding='utf-8')
            print(f"A sample README.md was created at '{readme_file_path}'.")
            readme_content_was_changed = True
        except Exception as e:
            print(f"Error creating sample README.md: {e}")
            return False

    try:
        current_readme_content_str = readme_file_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading README.md content from '{readme_file_path}': {e}")
        return False

    app_list_for_readme_md = []
    if app_names_list:
        for app_name_item in sorted(app_names_list):
            app_list_for_readme_md.append(app_name_item)
    else:
        app_list_for_readme_md.append("(هنوز هیچ نرم‌افزاری به این مخزن اضافه نشده است.)")
    
    formatted_apps_as_string = "\n".join(app_list_for_readme_md)

    if current_readme_content_str: # Ensure content was read
        start_index_placeholder = current_readme_content_str.find(APP_LIST_START_PLACEHOLDER)
        end_index_placeholder = current_readme_content_str.find(APP_LIST_END_PLACEHOLDER)

        if start_index_placeholder != -1 and end_index_placeholder != -1 and end_index_placeholder > start_index_placeholder:
            content_before_list_section = current_readme_content_str[:start_index_placeholder + len(APP_LIST_START_PLACEHOLDER)]
            if not content_before_list_section.endswith(('\n', '\r\n')):
                content_before_list_section += '\n'
            
            content_after_list_section = current_readme_content_str[end_index_placeholder:]
            
            apps_list_to_insert = formatted_apps_as_string
            if not apps_list_to_insert.endswith(('\n', '\r\n')):
                apps_list_to_insert += '\n'
                
            new_readme_full_content = f"{content_before_list_section}{apps_list_to_insert}{content_after_list_section}"
            
            if new_readme_full_content != current_readme_file_content:
                try:
                    readme_file_path.write_text(new_readme_full_content, encoding='utf-8')
                    print("README.md was updated with the new list of applications.")
                    readme_content_was_changed = True
                except Exception as e:
                    print(f"Error writing updated README.md: {e}")
            else:
                print("README.md application list is already up-to-date.")
        else:
            print(f"Warning: Placeholders '{APP_LIST_START_PLACEHOLDER}' and/or '{APP_LIST_END_PLACEHOLDER}' not found in README.md.")
            print("The application list was not updated. Please add the placeholders to your README.md file (inside the ```text block under ## Packages).")
    else:
         print(f"Warning: README.md content is not available for placeholder processing (it might be empty or unreadable).")
    
    return readme_content_was_changed

def main():
    repo_root = Path(".").resolve() 
    bucket_dir = repo_root / BUCKET_SUBDIRECTORY 
    readme_file = repo_root / README_FILE_NAME 

    print(f"Script to update manifests in '{bucket_dir}' started.")
    print("---------------------------------------------------------")

    if not bucket_dir.is_dir():
        print(f"Error: Bucket directory '{bucket_dir}' not found.")
        exit(1)

    manifest_files = list(bucket_dir.glob("*.json")) 
    processed_apps_list = [] 
    any_file_changed = False 

    if not manifest_files:
        print(f"No manifest files (.json) found in '{bucket_dir}'.")
    else:
        for manifest_file_path_obj in manifest_files: 
            app_name_from_file = manifest_file_path_obj.stem 
            print(f"\nProcessing manifest: {app_name_from_file} (File: {manifest_file_path_obj.name})")
            print("---------------------------")
            
            current_manifest_data = None
            
            print(f"Running 'scoop checkver \"{app_name_from_file}\" -u'...")
            try:
                # Try to run scoop checkver, first assuming scoop is in PATH, then trying a common install path.
                # The `Add Scoop shims to PATH` step in YAML should make 'scoop' directly callable.
                ps_command = f"$ProgressPreference = 'SilentlyContinue'; scoop checkver '{app_name_from_file}' -u"
                
                checkver_command_args_list = ["pwsh", "-Command", ps_command.strip()]
                
                checkver_process_result = subprocess.run( 
                    checkver_command_args_list, capture_output=True, text=True, check=False, encoding='utf-8', errors='replace'
                )
                if checkver_process_result.returncode != 0:
                    print(f"  Warning: Command `scoop checkver '{app_name_from_file}' -u` (attempt 1 via PATH) finished with exit code {checkver_process_result.returncode}.")
                    if checkver_process_result.stdout and checkver_process_result.stdout.strip(): print(f"    Scoop Checkver STDOUT:\n{checkver_process_result.stdout.strip()}")
                    if checkver_process_result.stderr and checkver_process_result.stderr.strip(): print(f"    Scoop Checkver STDERR:\n{checkver_process_result.stderr.strip()}")
                    
                    # Fallback attempt if scoop was not found via PATH (e.g. if GITHUB_PATH didn't work as expected for subprocess)
                    # This assumes a default user scoop installation path, which might not always be true for GitHub runners
                    # but it's a more robust attempt.
                    if "scoop: The term 'scoop' is not recognized" in checkver_process_result.stderr:
                        print("  Scoop not found in PATH, attempting to run via direct scoop.ps1 path...")
                        ps_command_direct = f"""
                        $ProgressPreference = 'SilentlyContinue'
                        $ScoopHome = "$env:USERPROFILE\\scoop"
                        $ScoopPs1 = Join-Path $ScoopHome "apps\\scoop\\current\\scoop.ps1"
                        if (Test-Path $ScoopPs1) {{
                            & $ScoopPs1 checkver '{app_name_from_file}' -u
                        }} else {{
                            Write-Error "scoop.ps1 not found at default user path: $ScoopPs1"
                            exit 1 # Exit if scoop can't be run, as checkver is critical
                        }}
                        """
                        checkver_command_args_list_direct = ["pwsh", "-NoProfile", "-Command", ps_command_direct.strip()]
                        scoop_checkver_result = subprocess.run(
                            checkver_command_args_list_direct, capture_output=True, text=True, check=False, encoding='utf-8', errors='replace'
                        )
                        if scoop_checkver_result.returncode != 0:
                             print(f"  Warning: Command `scoop checkver '{app_name_from_file}' -u` (attempt 2 via direct path) finished with exit code {scoop_checkver_result.returncode}.")
                             if scoop_checkver_result.stdout and scoop_checkver_result.stdout.strip(): print(f"    Scoop Checkver STDOUT:\n{scoop_checkver_result.stdout.strip()}")
                             if scoop_checkver_result.stderr and scoop_checkver_result.stderr.strip(): print(f"    Scoop Checkver STDERR:\n{scoop_checkver_result.stderr.strip()}")
                        else:
                             print(f"  'scoop checkver -u' for '{app_name_from_file}' (attempt 2 via direct path) executed successfully.")
                             if scoop_checkver_result.stdout and scoop_checkver_result.stdout.strip(): print(f"    Scoop Checkver Output:\n{scoop_checkver_result.stdout.strip()}")

                else: # First attempt was successful
                    print(f"  'scoop checkver -u' for '{app_name_from_file}' (attempt 1 via PATH) executed successfully.")
                    if scoop_checkver_result.stdout and scoop_checkver_result.stdout.strip(): print(f"    Scoop Checkver Output:\n{scoop_checkver_result.stdout.strip()}")
            
            except FileNotFoundError: # This is for pwsh itself not found
                print("  Error: 'pwsh' (PowerShell) not found. Cannot run 'scoop checkver'.")
            except Exception as e: # Other exceptions during subprocess call
                print(f"  Warning: An unexpected error occurred during 'scoop checkver \"{app_name_from_file}\" -u': {e}")

            try:
                with open(manifest_file_path_obj, 'r', encoding='utf-8-sig') as f: 
                    current_manifest_data = json.load(f)
            except Exception as e:
                print(f"  Error reading or parsing JSON manifest file '{manifest_file_path_obj}': {e}")
                any_file_actually_changed_in_run = True; continue

            url_for_download = None; hash_in_file = None 
            path_keys_for_hash = [] 

            if current_manifest_data.get("architecture", {}).get("64bit", {}).get("url"):
                url_for_download = current_manifest_data["architecture"]["64bit"]["url"]
                hash_in_file = current_manifest_data["architecture"]["64bit"].get("hash")
                path_keys_for_hash = ["architecture", "64bit", "hash"]
            elif current_manifest_data.get("url"):
                url_for_download = current_manifest_data["url"]
                hash_in_file = current_manifest_data.get("hash")
                path_keys_for_hash = ["hash"]
            
            if not url_for_download:
                print(f"  Warning: 'url' field not found or empty in manifest '{name_of_app}'. Skipping hash update.")
                processed_apps_list.append(name_of_app)
                continue
            
            print(f"  Download URL found: {url_for_download}")
            print(f"  Current hash in manifest: {hash_in_file}")

            temp_download_dir = repository_root_directory / "temp_scoop_dl_py_final" 
            temp_download_dir.mkdir(exist_ok=True)
            original_filename = os.path.basename(url_for_download.split('?')[0]) 
            safe_filename_for_temp = "".join(c if c.isalnum() or c in ['.', '-', '_'] else '_' for c in original_filename) 
            if not safe_filename_for_temp: safe_filename_for_temp = "downloaded_asset" 
            temp_file_full_path = temp_download_dir / f"{name_of_app}_{safe_filename_for_temp}.tmp" 

            download_completed_ok = download_file_from_url(url_for_download, temp_file_full_path) 
            newly_calculated_hash_value = None 

            if download_completed_ok:
                newly_calculated_hash_value = calculate_sha256_hash(temp_file_full_path)
                if newly_calculated_hash_value:
                    print(f"  New calculated hash for '{name_of_app}': {newly_calculated_hash_value}")
            
            if temp_file_full_path.exists():
                try: os.remove(temp_file_full_path)
                except Exception as e_rm: print(f"    Warning: Could not remove temporary file {temp_file_full_path}: {e_rm}")
            
            if temp_download_dir.exists() and not any(temp_download_dir.iterdir()):
                 try: temp_download_dir.rmdir()
                 except Exception as e_rmd: print(f"    Warning: Could not remove temporary directory {temp_download_dir}: {e_rmd}")

            manifest_needs_saving = False 
            if newly_calculated_hash_value and hash_in_file != newly_calculated_hash_value:
                print(f"  New hash ({newly_calculated_hash_value}) for '{name_of_app}' differs from current manifest hash ({hash_in_file}). Updating hash...")
                
                target_dict = current_manifest_data 
                if path_keys_for_hash == ["architecture", "64bit", "hash"]:
                    if "architecture" in target_dict and "64bit" in target_dict["architecture"]:
                        target_dict["architecture"]["64bit"]["hash"] = newly_calculated_hash_value
                        manifest_needs_saving = True
                elif path_keys_for_hash == ["hash"]:
                    if "hash" in target_dict or hash_in_file is not None :
                        target_dict["hash"] = newly_calculated_hash_value
                        manifest_needs_saving = True
                
                if not manifest_needs_saving and (path_keys_for_hash == ["architecture", "64bit", "hash"] or path_keys_for_hash == ["hash"]):
                     print(f"  Warning: Hash key structure issue in manifest '{name_of_app}'. Hash not updated.")

            elif newly_calculated_hash_value:
                print(f"  Calculated hash for '{name_of_app}' is identical to the hash in the manifest. No hash update needed.")
            else:
                print(f"  Hash for '{name_of_app}' was not updated due to previous download/calculation errors.")
                any_file_actually_changed_in_run = True 

            if manifest_needs_saving:
                 try:
                    with open(manifest_file_path_obj, 'w', encoding='utf-8') as f: 
                        json.dump(current_manifest_data, f, indent=4, ensure_ascii=False)
                    print(f"  Manifest file '{name_of_app}' was successfully updated with the new hash.")
                    any_file_actually_changed_in_run = True
                 except Exception as e:
                    print(f"  Error saving updated manifest file '{name_of_app}': {e}")
                    any_file_actually_changed_in_run = True
            
            processed_apps_list.append(name_of_app)
            print(f"Processing of manifest '{name_of_app}' finished.")
            print("---------------------------")

    # --- Update README.md ---
    # Use user's preferred bucket name and actual repo address
    user_chosen_bucket_name = "VpnClashFa" 
    actual_github_repo_address = "vpnclashfa-backup/VpnClashFaScoopBucket" 

    # If running in GitHub Actions, GITHUB_REPOSITORY will override the hardcoded actual_github_repo_address
    # This ensures the link in README is always correct for the current repository.
    # The bucket_name_for_display_param will still be user_chosen_bucket_name for the 'scoop bucket add' command text.
    github_repo_env_var = os.environ.get("GITHUB_REPOSITORY")
    if github_repo_env_var:
        actual_github_repo_address = github_repo_env_var # Use the actual repo from environment

    readme_was_changed_by_script = update_readme_file( 
        readme_file_full_path, 
        processed_apps_list, 
        user_chosen_bucket_name, # This is the name for "scoop bucket add NAME ..."
        actual_github_repo_address # This is for the URL [github.com/OWNER/REPO.git](https://github.com/OWNER/REPO.git)
    )

    print("\n=========================================================")
    if any_file_actually_changed_in_run or readme_was_changed_by_script :
        print("Update operation completed. Some files may have been modified or errors occurred.")
    else:
        print("Update operation for all manifests completed successfully (or no changes were needed).")

if __name__ == "__main__":
    main()
