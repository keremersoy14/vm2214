#!/usr/bin/env python3
"""
grabber_safe.py
- Fetch recent PDF entries from MalwareBazaar via the 'bazaar' CLI
- Skip SHAs already recorded in STATE
- Download new samples and move ZIPs into OUT_DIR
- Append each downloaded SHA to STATE
"""

import os
import sys
import json
import shlex
import subprocess
import time
import glob
import shutil

# Config
STATE = os.path.expanduser("~/.mb_seen_pdfs.txt")
OUT_DIR = os.path.expanduser("~/mb_downloads")
LIMIT = int(os.getenv("MB_LIMIT", "200"))   # how many recent entries to check
SLEEP_BETWEEN = 0.5                         # gentle pause between downloads

os.makedirs(OUT_DIR, exist_ok=True)

def run(cmd):
    """Run a shell command (shlex) and return stdout text (raise on nonzero)."""
    p = subprocess.run(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed ({cmd!r}): {p.stderr.strip()}")
    return p.stdout

def load_seen():
    if not os.path.exists(STATE):
        return set()
    with open(STATE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def append_seen(sha):
    # ensure directory exists
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "a") as f:
        f.write(sha + "\n")

def find_new_zips(before_set):
    """Return newly-created zip files in cwd compared to before_set (full paths)."""
    after = set(glob.glob("*.zip"))
    new = after - before_set
    return sorted(new)

def download_sha_and_move(sha):
    """Download using bazaar CLI and move any created zip(s) to OUT_DIR."""
    # record zips that existed before
    before = set(glob.glob("*.zip"))
    # run download (may write one or more zips)
    run(f"bazaar query hash {sha} --download")
    # allow small filesystem settle
    time.sleep(0.1)
    new_zips = find_new_zips(before)
    if not new_zips:
        # sometimes CLI writes into other folder — try to detect any zip modified recently
        # fallback: search home for newest zip within last minute (best-effort)
        candidates = sorted(glob.glob(os.path.expanduser("~/") + "**/*.zip", recursive=True),
                            key=os.path.getmtime, reverse=True)
        # pick top candidate if it's very fresh
        if candidates:
            top = candidates[0]
            # if modified in last 120 seconds, assume it's ours
            if (time.time() - os.path.getmtime(top)) < 120:
                new_zips = [top]
    # move found zips to OUT_DIR
    moved = []
    for z in new_zips:
        src = z
        dst = os.path.join(OUT_DIR, os.path.basename(z))
        shutil.move(src, dst)
        moved.append(dst)
    return moved

def clean_json_from_output(out_text):
    """Extract first {...} object from text and parse it."""
    start = out_text.find("{")
    end = out_text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in CLI output")
    return json.loads(out_text[start:end])

def main():
    seen = load_seen()
    print(f"Loaded {len(seen)} seen SHAs from {STATE}")

    # Fetch recent PDFs as JSON from bazaar CLI
    print("Querying MalwareBazaar for recent PDF entries...")
    raw = run(f"bazaar query filetype pdf --limit {LIMIT} --json")
    try:
        data = clean_json_from_output(raw)
    except Exception as e:
        print("Failed to parse JSON from bazaar output:", e, file=sys.stderr)
        print("Raw output starts:", raw[:400].replace("\n", "\\n"))
        sys.exit(1)

    items = data.get("data", [])
    print(f"API returned {len(items)} items; scanning for new SHAs...")

    new_shas = []
    for it in items:
        sha = it.get("sha256_hash") or it.get("sha256")
        if not sha:
            continue
        if sha in seen:
            continue
        new_shas.append(sha)

    if not new_shas:
        print("No new PDF samples found. Exiting.")
        return

    print(f"Found {len(new_shas)} new SHAs to download (will process in API order).")
    for sha in new_shas:
        print("-> Downloading", sha)
        try:
            moved_files = download_sha_and_move(sha)
            if moved_files:
                for m in moved_files:
                    print("   moved to", m)
            else:
                print("   WARNING: download succeeded but no new zip detected (see fallback).")
            append_seen(sha)
        except Exception as e:
            print("   Download failed for", sha, ":", e, file=sys.stderr)
        time.sleep(SLEEP_BETWEEN)

if __name__ == "__main__":
    main()
