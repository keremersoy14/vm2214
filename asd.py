#!/usr/bin/env python3
import os
import zipfile

source_dir = "/path/to/zips"
dest_dir = "/path/to/output"
password = b"infected"

os.makedirs(dest_dir, exist_ok=True)

for file in os.listdir(source_dir):
    if file.lower().endswith(".zip"):
        zip_path = os.path.join(source_dir, file)
        print(f"Unzipping {file}...")

        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(path=dest_dir, pwd=password)

print("Done.")
