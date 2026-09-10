# Observations Database Extractor
This module is responsible for extracting the `observations.db` database from iOS or iPadOS device backup.
It handles both encrypted and unencrypted backups, decrypting them if necessary, and locates the required database file within the backup structure.

## Installation
Install required dependencies using the provided installation script:
```bash
chmod +x install_tools.sh
bash install_tools.sh
```
Or install [libimobiledevice](https://libimobiledevice.org/#downloads) and [Mobile Verification Toolkit](https://docs.mvt.re/en/latest/install/) manually.

## Usage
> [!warning]
> The script copies the entire backup of the connected device onto your computer. Please ensure you have sufficient disk space before proceeding.

1. Connect your iOS or iPadOS device to your computer via USB.
2. Run the `usb_backup.py` script with:
```bash
python3 usb_backup.py
```
3. It may prompt for the backup encryption password if the backup is encrypted. The extracted `observations.db` database will be saved in the working directory.
