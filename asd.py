#!/usr/bin/env python3

import os
import subprocess

# Folder containing the .zip files
source_dir = "/home/kali/Desktop"          # <-- change if needed

# Folder where everything will be extracted
dest_dir = "/home/kali/Desktop/unzipped_s" # <-- change if you want

password = "infected"

os.makedirs(dest_dir, exist_ok=True)

for fname in os.listdir(source_dir):
    if fname.lower().endswith(".zip"):
        zip_path = os.path.join(source_dir, fname)
        print(f"Unzipping {zip_path} ...")

        # 7z x -pPASSWORD -y ZIPFILE -oOUTPUT_DIR
        result = subprocess.run(
            ["7z", "x", f"-p{password}", "-y", zip_path, f"-o{dest_dir}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode == 0:
            print(f"  -> OK")
        else:
            print(f"  -> FAILED ({result.returncode})")
            print(result.stderr)

print("Done.")
