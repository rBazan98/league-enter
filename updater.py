import os
import sys
import time
import shutil
import requests
import tempfile
import subprocess
import psutil
import logging

REPO = "rBazan98/league-enter"
EXE_NAME = "league-enter.exe"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S"
)

def get_download_url():
    url = f"https://api.github.com/repos/{REPO}/releases/latest"
    response = requests.get(url, timeout=5)
    if response.status_code != 200:
        raise Exception(f"GitHub API error: status code {response.status_code}")
    assets = response.json().get("assets", [])
    asset = next((a for a in assets if a["name"] == EXE_NAME), None)
    if not asset:
        raise Exception(f"Executable '{EXE_NAME}' not found in release assets.")
    return asset["browser_download_url"]

def download_update(dest_path):
    url = get_download_url()
    logging.info("Downloading update...")
    with requests.get(url, stream=True, timeout=10) as r:
        if r.status_code != 200:
            raise Exception(f"Failed to download file: HTTP {r.status_code}")
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(r.raw, f)
    logging.info("Download complete.")

def wait_for_process_to_exit(pid):
    try:
        p = psutil.Process(int(pid))
        logging.info(f"Waiting for process {pid} to exit...")
        p.wait(timeout=60)
    except Exception:
        pass  # Process already exited or does not exist

def apply_update(old_path, new_path, relaunch=False, retries=5, delay=1):
    logging.info(f"Replacing '{old_path}'...")
    for attempt in range(retries):
        try:
            shutil.copy2(new_path, old_path)
            os.remove(new_path)
            logging.info("Update applied successfully.")
            if relaunch:
                subprocess.Popen([old_path])
            return
        except PermissionError:
            logging.warning(f"Permission denied. Retrying in {delay} sec...")
            time.sleep(delay)
    raise Exception("Failed to replace the executable after multiple attempts.")

if __name__ == "__main__":
    temp_dir = tempfile.mkdtemp()
    new_exe = os.path.join(temp_dir, "league-enter-new.exe")

    try:
        download_update(new_exe)

        if len(sys.argv) == 3:
            # Classic mode: wait for process and relaunch
            pid = sys.argv[1]
            old_exe = sys.argv[2]
            wait_for_process_to_exit(pid)
            time.sleep(1)
            apply_update(old_exe, new_exe, relaunch=True)

        elif len(sys.argv) == 1:
            # Manual mode: just replace local exe
            script_dir = os.path.dirname(os.path.abspath(__file__))
            target_exe = os.path.join(script_dir, EXE_NAME)
            apply_update(target_exe, new_exe, relaunch=False)
            logging.info(f"'{EXE_NAME}' has been updated manually.")

        else:
            raise Exception("Usage:\n  updater.py             # manual mode\n  updater.py <pid> <exe> # auto-update mode")

    except Exception as e:
        logging.error(f"Update failed: {e}")
        time.sleep(5)
        sys.exit(1)