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
    user_bucket_name: str,
    github_repo_address: str
) -> bool:
    print(f"\nAttempting to update README.md at: {readme_file_path}")
    repo_git_url = f"https://github.com/{github_repo_address}.git"
    readme_was_changed = False

    if not readme_file_path.exists():
        print(f"README.md not found at '{readme_file_path}'. Creating a sample README.md.")
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
            return False

    try:
        current_readme_content = readme_file_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading README.md content from '{readme_file_path}': {e}")
        return False

    app_list_for_readme = []
    if app_names_list:
        for app_name in sorted(app_names_list):
            app_list_for_readme.append(app_name)
    else:
        app_list_for_readme.append("(هنوز هیچ نرم‌افزاری به این مخزن اضافه نشده است.)")
    
    formatted_app_list = "\n".join(app_list_for_readme)

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
            list_to_insert = formatted_app_list
            if not list_to_insert.endswith(('\n', '\r\n')):
                list_to_insert += '\n'
            new_readme_content = f"{content_before}{list_to_insert}{content_after}"
            
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
            print(f"Warning: Placeholders '{start_placeholder}' and/or '{end_placeholder}' not found in README.md.")
    else:
         print(f"Warning: README.md content is not available for placeholder processing.")
    
    return readme_was_changed

def main():
    repo_root = Path(".").resolve()
    bucket_dir = repo_root / BUCKET_SUBDIRECTORY
    readme_file = repo_root / README_FILE_NAME

    print(f"Python script started: Updating hashes and README in '{bucket_dir}'.")
    print("---------------------------------------------------------")

    if not bucket_dir.is_dir():
        print(f"Error: Bucket directory '{bucket_dir}' not found.")
        exit(1)

    manifest_files = list(bucket_dir.glob("*.json"))
    processed_app_names = []
    any_manifest_hash_updated = False

    if not manifest_files:
        print(f"No manifest files (.json) found in '{bucket_dir}'.")
    else:
        for manifest_file_path in manifest_files:
            app_name = manifest_file_path.stem
            print(f"\nProcessing manifest for hash update: {app_name} (File: {manifest_file_path.name})")
            print("---------------------------")
            
            manifest_data = None
            try:
                with open(manifest_file_path, 'r', encoding='utf-8-sig') as f:
                    manifest_data = json.load(f)
            except Exception as e:
                print(f"  Error reading or parsing JSON manifest file '{manifest_file_path}': {e}")
                processed_app_names.append(app_name) # Add to list for README even if processing fails here
                continue

            download_url = None; current_hash = None
            hash_path_keys = []

            if manifest_data.get("architecture", {}).get("64bit", {}).get("url"):
                download_url = manifest_data["architecture"]["64bit"]["url"]
                current_hash = manifest_data["architecture"]["64bit"].get("hash")
                hash_path_keys = ["architecture", "64bit", "hash"]
            elif manifest_data.get("url"):
                download_url = manifest_data["url"]
                current_hash = manifest_data.get("hash")
                hash_path_keys = ["hash"]
            
            if not download_url:
                print(f"  Warning: 'url' field not found or empty in manifest '{app_name}'. Skipping.")
                processed_app_names.append(app_name)
                continue
            
            print(f"  Download URL: {download_url}")
            print(f"  Current hash: {current_hash}")

            temp_dl_dir = repo_root / "temp_scoop_downloads_py_hash_readme"
            temp_dl_dir.mkdir(exist_ok=True)
            url_fname_part = os.path.basename(download_url.split('?')[0])
            safe_tmp_fname = "".join(c if c.isalnum() or c in ['.', '-', '_'] else '_' for c in url_fname_part)
            if not safe_tmp_fname: safe_tmp_fname = "dl_asset"
            tmp_file_location = temp_dl_dir / f"{app_name}_{safe_tmp_fname}.tmp"

            download_ok = download_file_from_url(download_url, tmp_file_location)
            new_hash = None

            if download_ok:
                new_hash = calculate_sha256_hash(tmp_file_location)
                if new_hash:
                    print(f"  New calculated hash: {new_hash}")
            
            if tmp_file_location.exists():
                try: os.remove(tmp_file_location)
                except Exception as e_rm: print(f"    Warning: Could not remove temp file {tmp_file_location}: {e_rm}")
            if temp_dl_dir.exists() and not any(temp_dl_dir.iterdir()):
                try: temp_dl_dir.rmdir()
                except Exception as e_rmd: print(f"    Warning: Could not remove temp dir {temp_dl_dir}: {e_rmd}")

            manifest_hash_updated = False
            if new_hash and current_hash != new_hash:
                print(f"  New hash ({new_hash}) differs from current ({current_hash}). Updating manifest...")
                target_dict = manifest_data
                if hash_path_keys == ["architecture", "64bit", "hash"]:
                    if "architecture" in target_dict and "64bit" in target_dict["architecture"]:
                        target_dict["architecture"]["64bit"]["hash"] = new_hash
                        manifest_hash_updated = True
                elif hash_path_keys == ["hash"]:
                    if "hash" in target_dict or current_hash is not None:
                        target_dict["hash"] = new_hash
                        manifest_hash_updated = True
                
                if not manifest_hash_updated and hash_path_keys: # Only warn if we expected to update
                     print(f"  Warning: Hash key structure issue in manifest '{app_name}'. Hash not updated.")

            elif new_hash:
                print(f"  Hashes match. No hash update needed for '{app_name}'.")
            else:
                print(f"  Hash for '{app_name}' not updated due to download/calculation errors.")
                any_manifest_updated = True # Mark as issue for overall status

            if manifest_hash_updated:
                 try:
                    with open(manifest_file_path, 'w', encoding='utf-8') as f:
                        json.dump(manifest_data, f, indent=4, ensure_ascii=False)
                    print(f"  Manifest '{app_name}' updated successfully with new hash.")
                    any_manifest_updated = True
                 except Exception as e:
                    print(f"  Error saving updated manifest '{app_name}': {e}")
                    any_manifest_updated = True
            
            processed_app_names.append(app_name)
            print(f"Processing of manifest '{app_name}' finished.")
            print("---------------------------")

    # --- Update README.md ---
    github_repo_env = os.environ.get("GITHUB_REPOSITORY")
    # Use user's specific preferred bucket name for display in README 'scoop bucket add' command
    bucket_name_for_readme = "VpnClashFa" 
    # Use actual repo address, try to derive it, fallback to user's specific repo
    actual_repo_for_readme_link = "vpnclashfa-backup/VpnClashFaScoopBucket" 

    if github_repo_env:
        actual_repo_for_readme_link = github_repo_env
    else:
        try:
            origin_url_proc = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=False, encoding='utf-8', errors='replace')
            if origin_url_proc.returncode == 0:
                origin_url = origin_url_proc.stdout.strip()
                match = re.search(r'github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?$', origin_url)
                if match:
                    owner, repo = match.groups()
                    actual_repo_for_readme_link = f"{owner}/{repo}"
                else:
                    print("Warning: Could not parse GitHub repo name from git remote for README. Using hardcoded default.")
            else:
                print("Warning: 'git remote get-url origin' failed. Using hardcoded default README repo info.")
        except Exception as e:
            print(f"Warning: Error determining repo info from git for README: {e}. Using hardcoded defaults.")

    readme_modified = update_readme_file(
        readme_file,
        processed_app_names,
        bucket_name_for_readme, # This is 'VpnClashFa'
        actual_repo_for_readme_link # This is 'owner/repo'
    )

    print("\n=========================================================")
    if any_manifest_updated or readme_modified :
        print("Update operation completed. Some files may have been modified or errors occurred.")
    else:
        print("Update operation for all manifests completed successfully (no changes were needed).")

if __name__ == "__main__":
    main()
