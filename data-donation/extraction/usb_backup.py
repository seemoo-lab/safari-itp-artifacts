import subprocess
import tempfile
import os
import sys
import sqlite3
import logging
import plistlib

from shutil import which
from typing import List

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

EXTERNAL_PATH = None # Adjust if needed, e.g., "/Volumes/UNTITLED"

SAFARI_DOMAIN = "AppDomain-com.apple.mobilesafari"
WEBKIT_STATS_PATH = "Library/WebKit/WebsiteData/ResourceLoadStatistics/observations.db"
OUTPUT_PATH = "observations.db"

def run_command(command_list: List[str]) -> str:
    try:
        logging.debug(f"Running command: {' '.join(command_list)}")
        result = subprocess.run(
            command_list, 
            capture_output=True, 
            text=True, 
            check=True
        )
        
        logging.debug(f"Command completed with result: {result.stdout.strip()}")
        return result.stdout.strip()

    except subprocess.CalledProcessError as e:
        logging.warning(f"Error running command: {e}")

        if e.stdout:
            logging.info(f"Command Standard Output: {e.stdout}")
            return e.stdout.strip()

        if e.stderr:
            logging.error(f"Error Details:\n{e.stderr}")
            return e.stderr.strip()

    except FileNotFoundError:
        logging.error(f"Command not found: {command_list[0]}")
        sys.exit(1)

def locate_file_in_manifest(manifest_db_path: str, domain: str, relative_path: str) -> str:

    # check if manifest.db exists
    if not os.path.isfile(manifest_db_path):
        logging.error(f"[-] Manifest.db not found in decrypted backup at {manifest_db_path}.")
        sys.exit(1)

    try:
        conn = sqlite3.connect(manifest_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT fileID FROM Files WHERE domain = ? AND relativePath = ?", (domain, relative_path))
        row = cursor.fetchone()
        conn.close()
    
        if row:
            return row[0] # fileID
        
        # no row, something's wrong
        return None
        
    except sqlite3.Error as e:
        logging.error(f"SQLite error: {e}")
        return None

def extract_observations_db(file_id: str, decrypted_dest: str, output_path: str) -> str:
    
    subdir = file_id[:2]
    file_path = os.path.join(decrypted_dest, subdir, file_id)
    if os.path.isfile(file_path):
        subprocess.run(["cp", file_path, output_path], check=True)
        return output_path
    
    # file not found
    return None

def check_program_on_path(program_name: str) -> bool:
    return which(program_name) is not None


def main():
    print("\n============================================")
    print("Safari observations.db extractor from iPhone/iPad Backup\n")
    print("This tool creates a local backup of your iOS device via USB,\n"
          "decrypts it if encrypted, and extracts the observations.db database used by Safari.")
    print("============================================\n")

    # check for required programs
    if not check_program_on_path("idevicebackup2"):
        print("\nError: idevicebackup2 not found in PATH. Please install libimobiledevice.")
        sys.exit(1)

    if not check_program_on_path("mvt-ios"):
        print("\nError: mvt-ios not found in PATH. Please install Mobile Verification Toolkit (MVT).")
        sys.exit(1)

    # make temp directory
    with tempfile.TemporaryDirectory(dir=EXTERNAL_PATH) as tmp_dir:
        logging.debug(f"Created temporary directory at {tmp_dir}")

        backup_root = os.path.join(tmp_dir, "backup")
        decrypted_root = os.path.join(tmp_dir, "decrypted")

        # ensure directories exist
        os.makedirs(backup_root, exist_ok=True)
        os.makedirs(decrypted_root, exist_ok=True)

        # Create Backup
        print("Creating Backup...")
        print("Ensure your device is connected via USB. You may be prompted to trust this computer on your device.")
        print("After entering your PIN on the device, the backup process will begin.")
        print("This may take several minutes...")

        backup_cmd = ["idevicebackup2", "backup", "--full", backup_root]
        output = run_command(backup_cmd)
        if "No device found." in output:
            print("\nError: No device found. Please ensure your device is connected and trusted.")
            sys.exit(1)

        # find the latest created backup directory
        try:
            list_subfolders_with_paths = [f.path for f in os.scandir(backup_root) if f.is_dir()]
            if not list_subfolders_with_paths:
                print(f"\nError: No backup folder found created in {backup_root}")
                sys.exit(1)
            
            # assume the latest folder is the one we just made
            latest_backup_dir = max(list_subfolders_with_paths, key=os.path.getmtime)
            logging.debug(f"Detected backup directory: {latest_backup_dir}")
        except Exception as e:
            print(f"\nError: Cannot find backup directory: {e}")
            sys.exit(1)

        # check if the backup is encrypted
        manifest_path = os.path.join(latest_backup_dir, "Manifest.plist")
        logging.debug(f"Reading Manifest.plist at: {manifest_path}")
        with open(manifest_path, 'rb') as f:
            data = plistlib.load(f)

        is_encrypted = data.get('IsEncrypted', False)
        print(f"Backup encryption status: {'Encrypted' if is_encrypted else 'Not Encrypted'}")
        if is_encrypted:

            backup_password = input("\nEnter the backup encryption password: ").strip()
            print("Decrypting backup. This may take several minutes...")
    
            device_udid = os.path.basename(latest_backup_dir)
            decrypted_dest = os.path.join(decrypted_root, device_udid)
            
            decrypt_cmd = [
                "mvt-ios", "decrypt-backup",
                "-p", backup_password,
                "-d", decrypted_dest,
                latest_backup_dir
            ]
            output = run_command(decrypt_cmd)
            if "Failed decrypting backup." in output:
                print(f"\nError: Failed to decrypt the backup. Please check your password and try again.")
                sys.exit(1)

        print("Extracting observations.db from decrypted backup...")

        # locate Manifest.db in the decrypted backup
        backup_folder = decrypted_dest if is_encrypted else latest_backup_dir
        manifest_db_path = os.path.join(backup_folder, "Manifest.db")
        file_id = locate_file_in_manifest(manifest_db_path, SAFARI_DOMAIN, WEBKIT_STATS_PATH)
        logging.debug(f"Located file ID: {file_id}")

        # copy observations.db to output path
        observations_path = extract_observations_db(file_id, backup_folder, OUTPUT_PATH)
        if not observations_path:
            print(f"\nError: File not found in backup: {file_id}")

    # after exiting the with block, temp directory is cleaned up
    print("Completed.")


if __name__ == "__main__":
    main()
