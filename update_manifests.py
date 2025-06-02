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
    readme_file_path_param: Path,
    list_of_app_names_param: list[str],
    bucket_name_for_display_param: str,
    github_repo_address_param: str
) -> bool:
    print(f"\nAttempting to update README.md at: {readme_file_path_param}")
    repo_url_for_readme_text = f"[https://github.com/](https://github.com/){github_repo_address_param}.git"
    readme_was_modified_flag = False

    if not readme_file_path_param.exists():
        print(f"Warning: README.md not found at '{readme_file_path_param}'. Creating a sample README.md.")
        default_readme_generated_content = f"""# مخزن Scoop شخصی {bucket_name_for_display_param}

به مخزن شخصی من برای نرم‌افزارهای Scoop خوش آمدید!
در اینجا مجموعه‌ای از مانیفست‌ها برای نصب آسان نرم‌افزارهای کاربردی، به خصوص ابزارهای مرتبط با شبکه و حریم خصوصی، قرار دارد. این مخزن به طور خودکار با استفاده از GitHub Actions به‌روزرسانی می‌شود.

## scoop

برای اضافه کردن این مخزن (Bucket) به Scoop خود و استفاده از نرم‌افزارهای آن، دستور زیر را در PowerShell اجرا کنید:

```powershell
scoop bucket add {bucket_name_for_display_param} {repo_url_for_readme_text}
scoop install {bucket_name_for_display_param}/<program-name>
```

## Packages

```text
{APP_LIST_START_PLACEHOLDER}
(این لیست به طور خودکار توسط اسکریپت به‌روزرسانی خواهد شد)
{APP_LIST_END_PLACEHOLDER}
```
---
می‌توانید وضعیت به‌روزرسانی‌های خودکار این مخزن را در صفحه Actions مشاهده کنید:
[صفحه وضعیت Actions](https://github.com/{github_repo_address_param}/actions)
"""
        try:
            readme_file_path_param.write_text(default_readme_generated_content, encoding='utf-8')
            print(f"A sample README.md was created at '{readme_file_path_param}'.")
            readme_was_modified_flag = True
        except Exception as e:
            print(f"Error creating sample README.md: {e}")
            return False # Indicate failure or no change if creation failed

    # Re-read content even if it was just created to ensure we have the latest
    try:
        current_readme_file_content = readme_file_path_param.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading README.md content from '{readme_file_path_param}' after potential creation: {e}")
        return False # Cannot proceed if README cannot be read

    generated_app_list_text_lines = []
    if list_of_app_names_param:
        for app_name_entry_item in sorted(list_of_app_names_param):
            generated_app_list_text_lines.append(app_name_entry_item)
    else:
        generated_app_list_text_lines.append("(هنوز هیچ نرم‌افزاری به این مخزن اضافه نشده است.)")
    
    final_formatted_app_list = "\n".join(generated_app_list_text_lines)

    start_placeholder_tag_text = APP_LIST_START_PLACEHOLDER
    end_placeholder_tag_text = APP_LIST_END_PLACEHOLDER

    if current_readme_file_content:
        start_tag_index = current_readme_file_content.find(start_placeholder_tag_text)
        end_tag_index = current_readme_file_content.find(end_placeholder_tag_text)

        if start_tag_index != -1 and end_tag_index != -1 and end_tag_index > start_tag_index:
            content_before_app_list = current_readme_file_content[:start_tag_index + len(start_placeholder_tag_text)]
            if not content_before_app_list.endswith(('\n', '\r\n')):
                content_before_app_list += '\n'
            
            content_after_app_list = current_readme_file_content[end_tag_index:]
            
            effective_app_list_for_readme = final_formatted_app_list
            if not effective_app_list_for_readme.endswith(('\n', '\r\n')):
                effective_app_list_for_readme += '\n'
                
            new_complete_readme_content = f"{content_before_app_list}{effective_app_list_for_readme}{content_after_app_list}"
            
            if new_complete_readme_content != current_readme_file_content:
                try:
                    readme_file_path_param.write_text(new_complete_readme_content, encoding='utf-8')
                    print("README.md was updated with the new list of applications.")
                    readme_was_modified_flag = True
                except Exception as e:
                    print(f"Error writing updated README.md: {e}")
            else:
                print("README.md application list is already up-to-date.")
        else:
            print(f"Warning: Placeholders '{start_placeholder_tag_text}' and/or '{end_placeholder_tag_text}' not found in README.md.")
            print("The application list was not updated. Please add the placeholders to your README.md file (inside the ```text block under ## Packages).")
    else:
         print(f"Warning: README.md content is not available for placeholder processing (it might be empty or unreadable).")
    
    return readme_was_modified_flag

def main():
    # These variables are defined at the beginning of main and should be in scope for the whole function
    repository_root_directory = Path(".").resolve() 
    actual_bucket_subdirectory = repository_root_directory / BUCKET_SUBDIRECTORY 
    readme_file_full_path = repository_root_directory / README_FILE_NAME 

    print(f"Script to update manifests in '{actual_bucket_subdirectory}' started.")
    print("---------------------------------------------------------")

    if not actual_bucket_subdirectory.is_dir():
        print(f"Error: Bucket directory '{actual_bucket_subdirectory}' not found.")
        exit(1)

    all_json_manifest_files = list(actual_bucket_subdirectory.glob("*.json")) 
    list_of_processed_app_names = [] 
    any_file_actually_changed_in_run = False 

    if not all_json_manifest_files:
        print(f"No manifest files (.json) found in '{actual_bucket_subdirectory}'.")
    else:
        for single_manifest_file in all_json_manifest_files: 
            name_of_app = single_manifest_file.stem 
            print(f"\nProcessing manifest: {name_of_app} (File: {single_manifest_file.name})")
            print("---------------------------")
            
            manifest_data_as_object = None 
            
            print(f"Running 'scoop checkver \"{name_of_app}\" -u'...")
            try:
                # Attempt to run scoop checkver, trying direct path if simple 'scoop' fails
                ps_command_for_checkver = f"""
                $ProgressPreference = 'SilentlyContinue'
                scoop checkver '{name_of_app}' -u
                if ($LASTEXITCODE -ne 0) {{
                    Write-Warning "scoop checkver via PATH failed (exit code $LASTEXITCODE). Trying direct path to scoop.ps1..."
                    $ScoopUserInstallDir = Join-Path $env:USERPROFILE "scoop"
                    $ScoopExecutable = Join-Path $ScoopUserInstallDir "apps\\scoop\\current\\scoop.ps1"
                    if (Test-Path $ScoopExecutable) {{
                        & $ScoopExecutable checkver '{name_of_app}' -u
                    }} else {{
                        Write-Error "scoop.ps1 not found at default user path: $ScoopExecutable. Cannot run checkver."
                        exit 1 # Exit if scoop can't be run, as checkver is critical
                    }}
                }}
                exit $LASTEXITCODE # Forward the exit code of the last command (scoop checkver)
                """
                # Use -Command for complex commands. -NoProfile might prevent scoop env setup, so removed.
                scoop_checkver_command_line_args = ["pwsh", "-Command", ps_command_for_checkver.strip()]
                
                scoop_checkver_execution_result = subprocess.run( 
                    scoop_checkver_command_line_args, capture_output=True, text=True, check=False, encoding='utf-8', errors='replace'
                )
                
                if scoop_checkver_execution_result.returncode != 0:
                    print(f"  Warning: 'scoop checkver '{name_of_app}' -u' process finished with exit code {scoop_checkver_execution_result.returncode}.")
                    if scoop_checkver_execution_result.stdout and scoop_checkver_execution_result.stdout.strip(): print(f"    Scoop Checkver STDOUT:\n{scoop_checkver_execution_result.stdout.strip()}")
                    if scoop_checkver_execution_result.stderr and scoop_checkver_execution_result.stderr.strip(): print(f"    Scoop Checkver STDERR:\n{scoop_checkver_execution_result.stderr.strip()}")
                else:
                    print(f"  'scoop checkver -u' for '{name_of_app}' executed successfully.")
                    if scoop_checkver_execution_result.stdout and scoop_checkver_execution_result.stdout.strip(): print(f"    Scoop Checkver Output:\n{scoop_checkver_execution_result.stdout.strip()}")
            
            except FileNotFoundError: 
                print("  Error: 'pwsh' (PowerShell) not found. Cannot run 'scoop checkver'.")
            except Exception as e: 
                print(f"  Warning: An unexpected error occurred during 'scoop checkver \"{name_of_app}\" -u': {e}")

            try:
                with open(single_manifest_file, 'r', encoding='utf-8-sig') as f: 
                    manifest_data_as_object = json.load(f)
            except Exception as e:
                print(f"  Error reading or parsing JSON manifest file '{single_manifest_file}': {e}")
                any_file_actually_changed_in_run = True; continue

            app_download_link = None; hash_value_from_json = None 
            keys_to_reach_hash_in_json = [] 

            if manifest_data_as_object.get("architecture", {}).get("64bit", {}).get("url"):
                app_download_link = manifest_data_as_object["architecture"]["64bit"]["url"]
                hash_value_from_json = manifest_data_as_object["architecture"]["64bit"].get("hash")
                keys_to_reach_hash_in_json = ["architecture", "64bit", "hash"]
            elif manifest_data_as_object.get("url"):
                app_download_link = manifest_data_as_object["url"]
                hash_value_from_json = manifest_data_as_object.get("hash")
                keys_to_reach_hash_in_json = ["hash"]
            
            if not app_download_link:
                print(f"  Warning: 'url' field not found or empty in manifest '{name_of_app}'. Skipping hash update.")
                list_of_processed_app_names.append(name_of_app)
                continue
            
            print(f"  Download URL found: {app_download_link}")
            print(f"  Current hash in manifest: {hash_value_from_json}")

            # This is where 'repository_root_directory' is used, it's defined at the start of main()
            temp_download_dir_path = repository_root_directory / "temp_scoop_downloads_python_final_v_action_fix" 
            temp_download_dir_path.mkdir(exist_ok=True)
            original_filename_from_url = os.path.basename(app_download_link.split('?')[0]) 
            sanitized_temporary_filename = "".join(c if c.isalnum() or c in ['.', '-', '_'] else '_' for c in original_filename_from_url) 
            if not sanitized_temporary_filename: sanitized_temporary_filename = "downloaded_asset_default_name" 
            full_path_to_temporary_downloaded_file = temp_download_dir_path / f"{name_of_app}_{sanitized_temporary_filename}.tmp" 

            download_was_ok = download_file_from_url(app_download_link, full_path_to_temporary_downloaded_file) 
            newly_calculated_file_hash = None 

            if download_was_ok:
                newly_calculated_file_hash = calculate_sha256_hash(full_path_to_temporary_downloaded_file)
                if newly_calculated_file_hash:
                    print(f"  New calculated hash for '{name_of_app}': {newly_calculated_file_hash}")
            
            if full_path_to_temporary_downloaded_file.exists():
                try: os.remove(full_path_to_temporary_downloaded_file)
                except Exception as e_rm_temp: print(f"    Warning: Could not remove temporary file {full_path_to_temporary_downloaded_file}: {e_rm_temp}")
            
            if temp_download_dir_path.exists() and not any(temp_download_dir_path.iterdir()): # Remove if empty
                 try: temp_download_dir_path.rmdir()
                 except Exception as e_rm_dir: print(f"    Warning: Could not remove temporary directory {temp_download_dir_path}: {e_rm_dir}")

            manifest_file_updated_due_to_hash = False 
            if newly_calculated_file_hash and hash_value_from_json != newly_calculated_file_hash:
                print(f"  New hash ({newly_calculated_file_hash}) for '{name_of_app}' differs from current manifest hash ({hash_value_from_json}). Updating hash...")
                
                target_dictionary_to_update = manifest_data_as_object 
                if keys_to_reach_hash_in_json == ["architecture", "64bit", "hash"]:
                    if "architecture" in target_dictionary_to_update and "64bit" in target_dictionary_to_update["architecture"]:
                        target_dictionary_to_update["architecture"]["64bit"]["hash"] = newly_calculated_file_hash
                        manifest_file_updated_due_to_hash = True
                elif keys_to_reach_hash_in_json == ["hash"]:
                    if "hash" in target_dictionary_to_update or hash_value_from_json is not None :
                        target_dictionary_to_update["hash"] = newly_calculated_file_hash
                        manifest_file_updated_due_to_hash = True
                
                if not manifest_file_updated_due_to_hash and (keys_to_reach_hash_in_json == ["architecture", "64bit", "hash"] or keys_to_reach_hash_in_json == ["hash"]):
                     print(f"  Warning: Hash key structure issue in manifest '{name_of_app}'. Hash not updated.")

            elif newly_calculated_file_hash:
                print(f"  Calculated hash for '{name_of_app}' is identical to the hash in the manifest. No hash update needed.")
            else:
                print(f"  Hash for '{name_of_app}' was not updated due to previous download/calculation errors.")
                any_file_actually_changed_in_run = True 

            if manifest_file_updated_due_to_hash:
                 try:
                    with open(single_manifest_file, 'w', encoding='utf-8') as f: 
                        json.dump(manifest_data_as_object, f, indent=4, ensure_ascii=False)
                    print(f"  Manifest file '{name_of_app}' was successfully updated with the new hash.")
                    any_file_actually_changed_in_run = True
                 except Exception as e:
                    print(f"  Error saving updated manifest file '{name_of_app}': {e}")
                    any_file_actually_changed_in_run = True
            
            list_of_processed_app_names.append(name_of_app)
            print(f"Processing of manifest '{name_of_app}' finished.")
            print("---------------------------")

    # --- Update README.md ---
    github_repository_env_variable_value = os.environ.get("GITHUB_REPOSITORY") 
    bucket_name_to_display_in_readme = "VpnClashFa" 
    repo_address_for_readme_file = "vpnclashfa-backup/VpnClashFaScoopBucket" 

    if github_repository_env_variable_value: 
        repo_name_parts_from_github_env = github_repository_env_variable_value.split('/') 
        if len(repo_name_parts_from_github_env) == 2:
            repo_address_for_readme_file = github_repository_env_variable_value
    else: 
        try:
            git_origin_url_command_output = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=False, encoding='utf-8', errors='replace') 
            if git_origin_url_command_output.returncode == 0:
                git_origin_url_string_value = git_origin_url_command_output.stdout.strip() 
                url_regex_match_object = re.search(r'github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?$', git_origin_url_string_value) 
                if url_regex_match_object:
                    git_repository_owner, git_repository_name = url_regex_match_object.groups() 
                    repo_address_for_readme_file = f"{git_repository_owner}/{git_repository_name}"
                else:
                    print("Warning: Could not parse GitHub repository name from git remote URL for README.")
            else:
                print("Warning: 'git remote get-url origin' failed. Using default README info.")
        except Exception as e:
            print(f"Warning: Could not determine repository info from git for README: {e}. Using default README info.")

    readme_was_modified_by_script_flag = update_readme_file( 
        readme_file_full_path, 
        list_of_processed_app_names, 
        bucket_name_to_display_in_readme, 
        repo_address_for_readme_file
    )

    print("\n=========================================================")
    if any_file_actually_changed_in_run or readme_was_modified_by_script_flag :
        print("Update operation completed. Some files may have been modified or errors occurred.")
    else:
        print("Update operation for all manifests completed successfully (or no changes were needed).")

if __name__ == "__main__":
    main()
