#!/usr/bin/env python3

import os
import zipfile

PASSWORD = b"infected"  # password must be bytes

def unzip_all_with_password(directory="."):
    # List all files in the given directory
    for filename in os.listdir(directory):
        if filename.lower().endswith(".zip"):
            zip_path = os.path.join(directory, filename)
            extract_dir = os.path.join(directory, filename[:-4])  # remove .zip

            print(f"[+] Processing: {zip_path}")
            # Make the output folder if it doesn't exist
            os.makedirs(extract_dir, exist_ok=True)

            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    # set password and extract all files
                    zf.extractall(path=extract_dir, pwd=PASSWORD)
                print(f"    -> Extracted to: {extract_dir}")
            except RuntimeError as e:
                # Wrong password or encrypted method not supported
                print(f"    [!] Failed to extract {filename}: {e}")
            except zipfile.BadZipFile as e:
                print(f"    [!] Bad zip file {filename}: {e}")
            except Exception as e:
                print(f"    [!] Unexpected error for {filename}: {e}")

if __name__ == "__main__":
    # current directory by default
    unzip_all_with_password(".")
