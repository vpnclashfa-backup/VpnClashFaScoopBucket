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
APP_LIST_START_PLACEHOLDER = "" # Correct placeholder
APP_LIST_END_PLACEHOLDER = ""   # Correct placeholder
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
    app_names: list[str],
    bucket_name_for_display: str,
    github_repo_address: str
) -> bool:
    print(f"\nAttempting to update README.md at: {readme_file_path}")
    repo_url_for_readme = f"https://github.com/{github_repo_address}.git"
    readme_content_changed = False

    if not readme_file_path.exists():
        print(f"Warning: README.md not found at '{readme_file_path}'. Creating a sample README.md.")
        default_readme_content = f"""# مخزن Scoop شخصی {bucket_name_for_display}

به مخزن شخصی من برای نرم‌افزارهای Scoop خوش آمدید!
در اینجا مجموعه‌ای از مانیفست‌ها برای نصب آسان نرم‌افزارهای کاربردی، به خصوص ابزارهای مرتبط با شبکه و حریم خصوصی، قرار دارد. این مخزن به طور خودکار با استفاده از GitHub Actions به‌روزرسانی می‌شود.

## scoop

برای اضافه کردن این مخزن (Bucket) به Scoop خود و استفاده از نرم‌افزارهای آن، دستور زیر را در PowerShell اجرا کنید:

```powershell
scoop bucket add {bucket_name_for_display} {repo_url_for_readme}
scoop install {bucket_name_for_display}/<program-name>
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
            readme_file_path.write_text(default_readme_content, encoding='utf-8')
            print(f"A sample README.md was created at '{readme_file_path}'.")
            readme_content_changed = True
        except Exception as e:
            print(f"Error creating sample README.md: {e}")
            # If README creation fails, we still want to try processing manifests,
            # but the overall "changed" status for git commit might be affected.
            # For now, we return False as README itself wasn't successfully handled.
            return False

    # Read content (either existing or just created)
    try:
        current_readme_content = readme_file_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading README.md content from '{readme_file_path}': {e}")
        return False

    app_list_lines = []
    if app_names:
        for app_name_item in sorted(app_names):
            app_list_lines.append(app_name_item)
    else:
        app_list_lines.append("(هنوز هیچ نرم‌افزاری به این مخزن اضافه نشده است.)")
    
    formatted_app_list_str = "\n".join(app_list_lines)

    # Using the correct global constants for placeholders
    start_placeholder = APP_LIST_START_PLACEHOLDER 
    end_placeholder = APP_LIST_END_PLACEHOLDER

    if current_readme_content:
        start_index = current_readme_content.find(start_placeholder)
        end_index = current_readme_content.find(end_placeholder)

        if start_index != -1 and end_index != -1 and end_index > start_index:
            content_before = current_readme_content[:start_index + len(start_placeholder)]
            if not content_before.endswith(('\n', '\r\n')):
                content_before += '\n'
            
            content_after = current_readme_content[end_index:]
            
            list_to_insert = formatted_app_list_str
            if not list_to_insert.endswith(('\n', '\r\n')):
                list_to_insert += '\n'
                
            new_readme_text = f"{content_before}{list_to_insert}{content_after}"
            
            if new_readme_text != current_readme_content:
                try:
                    readme_file_path.write_text(new_readme_text, encoding='utf-8')
                    print("README.md was updated with the new list of applications.")
                    if not readme_content_changed: readme_content_changed = True # Set if not already true
                except Exception as e:
                    print(f"Error writing updated README.md: {e}")
            else:
                print("README.md application list is already up-to-date.")
        else:
            print(f"Warning: Placeholders '{start_placeholder}' and/or '{end_placeholder}' not found in the existing README.md.")
            print("The application list was not updated. Please ensure placeholders are in your README.md (inside the ```text block under ## Packages).")
    else:
         print(f"Warning: README.md content is not available for placeholder processing (it might be empty or unreadable).")
    
    return readme_content_changed

def main():
    repo_root = Path(".").resolve() 
    bucket_dir = repo_root / BUCKET_SUBDIRECTORY 
    readme_file_path = repo_root / README_FILE_NAME 

    print(f"Script to update manifests in '{bucket_dir}' started.")
    print("---------------------------------------------------------")

    if not bucket_dir.is_dir():
        print(f"Error: Bucket directory '{bucket_dir}' not found.")
        exit(1)

    manifest_files = list(bucket_dir.glob("*.json")) 
    processed_app_names = [] 
    any_file_changed_this_run = False 

    if not manifest_files:
        print(f"No manifest files (.json) found in '{bucket_dir}'.")
    else:
        for manifest_file in manifest_files: 
            app_name = manifest_file.stem 
            print(f"\nProcessing manifest: {app_name} (File: {manifest_file.name})")
            print("---------------------------")
            
            current_manifest_obj = None
            
            print(f"Running 'scoop checkver \"{app_name}\" -u'...")
            try:
                # PowerShell command with fallback for scoop path
                ps_command_to_run = f"""
                $ProgressPreference = 'SilentlyContinue';
                scoop checkver '{app_name}' -u;
                if ($LASTEXITCODE -ne 0) {{
                    $ScoopCommandOutput = $Error[0].ToString() # Get the error message
                    if ($ScoopCommandOutput -match "The term 'scoop' is not recognized") {{
                        Write-Warning "scoop checkver via PATH failed. Trying direct path to scoop.ps1..."
                        $UserProfilePath = [Environment]::GetFolderPath('UserProfile')
                        $ScoopExePath = Join-Path $UserProfilePath "scoop\\apps\\scoop\\current\\scoop.ps1"
                        if (Test-Path $ScoopExePath) {{
                            & $ScoopExePath checkver '{app_name}' -u
                        }} else {{
                            Write-Error "scoop.ps1 not found at default user path: $ScoopExePath. Cannot run checkver."
                            exit 1 # Critical error if scoop cannot be run
                        }}
                    }}
                }}
                exit $LASTEXITCODE # Forward the actual exit code of scoop checkver
                """
                # Removed -NoProfile to allow environment/module loading
                checkver_process_args = ["pwsh", "-Command", ps_command_to_run.strip()] 
                
                checkver_result_obj = subprocess.run( 
                    checkver_process_args, capture_output=True, text=True, check=False, encoding='utf-8', errors='replace'
                )
                
                if checkver_result_obj.returncode != 0:
                    print(f"  Warning: 'scoop checkver '{app_name}' -u' process finished with exit code {checkver_result_obj.returncode}.")
                    if checkver_result_obj.stdout and checkver_result_obj.stdout.strip(): print(f"    Scoop Checkver STDOUT:\n{checkver_result_obj.stdout.strip()}")
                    if checkver_result_obj.stderr and checkver_result_obj.stderr.strip(): print(f"    Scoop Checkver STDERR:\n{checkver_result_obj.stderr.strip()}")
                else:
                    print(f"  'scoop checkver -u' for '{app_name}' executed successfully.")
                    if checkver_result_obj.stdout and checkver_result_obj.stdout.strip(): print(f"    Scoop Checkver Output:\n{checkver_result_obj.stdout.strip()}")
            
            except FileNotFoundError: 
                print("  Error: 'pwsh' (PowerShell) not found. Cannot run 'scoop checkver'.")
                any_file_changed_this_run = True # Mark as error for overall status
                continue # Skip to next app if pwsh is not found
            except Exception as e: 
                print(f"  Warning: An unexpected error occurred during 'scoop checkver \"{app_name}\" -u': {e}")
                # Continue to hash check, as checkver might have partially worked or failed gracefully

            try:
                with open(manifest_file, 'r', encoding='utf-8-sig') as f: 
                    current_manifest_obj = json.load(f)
            except Exception as e:
                print(f"  Error reading or parsing JSON manifest file '{manifest_file}': {e}")
                any_file_changed_this_run = True; continue

            download_url = None; current_hash = None 
            hash_json_path = [] 

            if current_manifest_obj.get("architecture", {}).get("64bit", {}).get("url"):
                download_url = current_manifest_obj["architecture"]["64bit"]["url"]
                current_hash = current_manifest_obj["architecture"]["64bit"].get("hash")
                hash_json_path = ["architecture", "64bit", "hash"]
            elif current_manifest_obj.get("url"):
                download_url = current_manifest_obj["url"]
                current_hash = current_manifest_obj.get("hash")
                hash_json_path = ["hash"]
            
            if not download_url:
                print(f"  Warning: 'url' field not found or empty in manifest '{app_name}'. Skipping hash update.")
                processed_apps_list.append(app_name)
                continue
            
            print(f"  Download URL found: {download_url}")
            print(f"  Current hash in manifest: {current_hash}")

            temp_download_dir = repo_root / "temp_scoop_downloads_py_v_final_action" 
            temp_download_dir.mkdir(exist_ok=True)
            url_filename = os.path.basename(download_url.split('?')[0]) 
            safe_temp_name = "".join(c if c.isalnum() or c in ['.', '-', '_'] else '_' for c in url_filename) 
            if not safe_temp_name: safe_temp_name = "scoop_downloaded_asset" 
            temp_file_location = temp_download_dir / f"{app_name}_{safe_temp_name}.tmp" 

            download_succeeded = download_file_from_url(download_url, temp_file_location) 
            calculated_hash_value = None 

            if download_succeeded:
                calculated_hash_value = calculate_sha256_hash(temp_file_location)
                if calculated_hash_value:
                    print(f"  New calculated hash for '{app_name}': {calculated_hash_value}")
            
            if temp_file_location.exists():
                try: os.remove(temp_file_location)
                except Exception as e_rm: print(f"    Warning: Could not remove temporary file {temp_file_location}: {e_rm}")
            
            if temp_download_dir.exists() and not any(temp_download_dir.iterdir()):
                 try: temp_download_dir.rmdir()
                 except Exception as e_rmd: print(f"    Warning: Could not remove temporary directory {temp_download_dir}: {e_rmd}")

            manifest_updated_this_iteration = False 
            if calculated_hash_value and current_hash != calculated_hash_value:
                print(f"  New hash ({calculated_hash_value}) for '{app_name}' differs from current manifest hash ({current_hash}). Updating hash...")
                
                target_dict_to_modify = current_manifest_obj 
                if hash_json_path == ["architecture", "64bit", "hash"]:
                    if "architecture" in target_dict_to_modify and "64bit" in target_dict_to_modify["architecture"]:
                        target_dict_to_modify["architecture"]["64bit"]["hash"] = calculated_hash_value
                        manifest_updated_this_iteration = True
                elif hash_json_path == ["hash"]:
                    if "hash" in target_dict_to_modify or current_hash is not None :
                        target_dict_to_modify["hash"] = calculated_hash_value
                        manifest_updated_this_iteration = True
                
                if not manifest_updated_this_iteration and (hash_json_path == ["architecture", "64bit", "hash"] or hash_json_path == ["hash"]):
                     print(f"  Warning: Hash key structure issue in manifest '{app_name}'. Hash not updated.")

            elif calculated_hash_value:
                print(f"  Calculated hash for '{app_name}' is identical to the hash in the manifest. No hash update needed.")
            else:
                print(f"  Hash for '{app_name}' was not updated due to previous download/calculation errors.")
                any_file_actually_changed_in_run = True 

            if manifest_updated_this_iteration:
                 try:
                    with open(manifest_file_path_obj, 'w', encoding='utf-8') as f: 
                        json.dump(current_manifest_obj, f, indent=4, ensure_ascii=False)
                    print(f"  Manifest file '{app_name}' was successfully updated with the new hash.")
                    any_file_actually_changed_in_run = True
                 except Exception as e:
                    print(f"  Error saving updated manifest file '{app_name}': {e}")
                    any_file_actually_changed_in_run = True
            
            processed_apps_list.append(app_name)
            print(f"Processing of manifest '{app_name}' finished.")
            print("---------------------------")

    # --- Update README.md ---
    # Use user's preferred bucket name and actual repo address from environment or git remote
    github_repo_from_env = os.environ.get("GITHUB_REPOSITORY") 
    display_bucket_name = "VpnClashFa" 
    actual_repo_address = "vpnclashfa-backup/VpnClashFaScoopBucket" 

    if github_repo_from_env: 
        actual_repo_address = github_repo_from_env
        # display_bucket_name remains VpnClashFa as per user request for 'scoop bucket add' command
    else: 
        try:
            origin_url_proc = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=False, encoding='utf-8', errors='replace') 
            if origin_url_proc.returncode == 0:
                origin_url_str = origin_url_proc.stdout.strip() 
                match_obj = re.search(r'github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?$', origin_url_str) 
                if match_obj:
                    owner_name, repo_actual_name = match_obj.groups() 
                    actual_repo_address = f"{owner_name}/{repo_actual_name}"
                else:
                    print("Warning: Could not parse GitHub repository name from git remote URL for README. Using defaults.")
            else:
                print("Warning: 'git remote get-url origin' failed. Using default README info.")
        except Exception as e:
            print(f"Warning: Could not determine repository info from git for README: {e}. Using default README info.")

    readme_was_modified = update_readme_file( 
        readme_file_full_path, 
        processed_apps_list, 
        display_bucket_name, 
        actual_repo_address
    )

    print("\n=========================================================")
    if any_file_actually_changed_in_run or readme_was_modified :
        print("Update operation completed. Some files may have been modified or errors occurred.")
    else:
        print("Update operation for all manifests completed successfully (or no changes were needed).")

if __name__ == "__main__":
    main()
