#!/usr/bin/env python3
"""
grabber_safe.py

- Requires: 'bazaar' CLI available in PATH and MB_AUTH_KEY exported in the shell.
- Usage: within your Kali VM:
    source ~/mb_venv/bin/activate
    export MB_AUTH_KEY="PASTE_YOUR_KEY"
    python3 grabber_safe.py

What it does:
- Query MalwareBazaar for recent PDFs (limit set by MB_LIMIT env or default 200)
- Skip SHAs already recorded in STATE (~/.mb_seen_pdfs.txt)
- Download new samples with bazaar CLI
- Move zip(s) created into OUT_DIR (~/mb_downloads)
- Append each successful SHA to STATE
"""

import os
import sys
import json
import shlex
import subprocess
import time
import glob
import shutil

# ------------------- Configuration -------------------
STATE = os.path.expanduser("~/.mb_seen_pdfs.txt")
OUT_DIR = os.path.expanduser("~/mb_downloads")
LIMIT = int(os.getenv("MB_LIMIT", "200"))   # how many recent entries to check
SLEEP_BETWEEN = float(os.getenv("MB_SLEEP", "0.5"))  # seconds between downloads
# -----------------------------------------------------

os.makedirs(OUT_DIR, exist_ok=True)

def run(cmd):
    """Run a command (using shlex.split) and return stdout, raise RuntimeError on non-zero."""
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
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "a") as f:
        f.write(sha + "\n")

def find_new_zips(before_set):
    """Return newly-created zip filenames in the current working directory compared to before_set."""
    after = set(glob.glob("*.zip"))
    new = after - before_set
    return sorted(new)

def download_sha_and_move(sha):
    """
    Download a SHA using bazaar CLI and move any created zip(s) to OUT_DIR.
    Returns list of destination paths moved.
    """
    # record current zip files in working dir
    before = set(glob.glob("*.zip"))
    # run the download
    run(f"bazaar query hash {sha} --download")
    # small settle
    time.sleep(0.15)
    new_zips = find_new_zips(before)

    # fallback: if no new zips in cwd, look for recently modified zip under home (best-effort)
    if not new_zips:
        candidates = sorted(glob.glob(os.path.expanduser("~/") + "**/*.zip", recursive=True),
                            key=lambda p: os.path.getmtime(p), reverse=True)
        if candidates:
            top = candidates[0]
            if (time.time() - os.path.getmtime(top)) < 180:
                new_zips = [top]

    moved = []
    for z in new_zips:
        src = z
        # If src is absolute path from fallback, keep src; otherwise it is relative filename
        if not os.path.isabs(src):
            src = os.path.abspath(src)
        dst = os.path.join(OUT_DIR, os.path.basename(src))
        try:
            shutil.move(src, dst)
        except Exception:
            # try copy+remove if move fails across filesystems
            shutil.copy2(src, dst)
            os.remove(src)
        moved.append(dst)
    return moved

def clean_json_from_output(out_text):
    """Extract the first top-level JSON object or array from text and parse it."""
    # find first '[' or '{'
    pos_bracket = out_text.find('[')
    pos_brace = out_text.find('{')

    if pos_bracket == -1 and pos_brace == -1:
        raise ValueError("No JSON object or array found in CLI output")

    if pos_bracket == -1:
        start = pos_brace
        open_ch, close_ch = '{', '}'
    elif pos_brace == -1:
        start = pos_bracket
        open_ch, close_ch = '[', ']'
    else:
        if pos_bracket < pos_brace:
            start = pos_bracket
            open_ch, close_ch = '[', ']'
        else:
            start = pos_brace
            open_ch, close_ch = '{', '}'

    # locate the last occurrence of the matching closing character
    end = out_text.rfind(close_ch)
    if end == -1:
        raise ValueError(f"No closing {close_ch} found in CLI output")

    candidate = out_text[start:end + 1]

    try:
        return json.loads(candidate)
    except Exception as e:
        # helpful debug output
        print("Failed parsing candidate JSON chunk:", e, file=sys.stderr)
        preview = candidate[:2000].replace("\n", "\\n")
        print("Candidate preview (first 2000 chars):", preview, file=sys.stderr)
        raise

def main():
    # quick environment checks
    if "MB_AUTH_KEY" not in os.environ:
        print("Warning: MB_AUTH_KEY not set in environment. Ensure you exported your abuse.ch API key.", file=sys.stderr)
    try:
        seen = load_seen()
    except Exception as e:
        print("Error reading state file:", e, file=sys.stderr)
        seen = set()

    print(f"Loaded {len(seen)} seen SHAs from {STATE}")

    # Query
    print("Querying MalwareBazaar for recent PDF entries...")
    try:
        raw = run(f"bazaar query filetype pdf --limit {LIMIT} --json")
    except RuntimeError as e:
        print("Error running bazaar CLI:", e, file=sys.stderr)
        sys.exit(1)

    try:
        data = clean_json_from_output(raw)
    except Exception as e:
        print("Failed to parse JSON from bazaar output:", e, file=sys.stderr)
        print("Raw output preview:", raw[:1000].replace("\n", "\\n"), file=sys.stderr)
        sys.exit(1)

    # The API may return a list (top-level array) or an object with "data": [...]
    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and "data" in data:
        items = data.get("data", [])
    else:
        print("Unexpected JSON structure from bazaar CLI; exiting.", file=sys.stderr)
        sys.exit(1)

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

    print(f"Found {len(new_shas)} new SHAs to download (processing in API order).")

    for sha in new_shas:
        print("-> Downloading", sha)
        try:
            moved_files = download_sha_and_move(sha)
            if moved_files:
                for m in moved_files:
                    print("   moved to", m)
            else:
                print("   WARNING: download succeeded but no new zip detected (no file moved).")
            append_seen(sha)
            # mark as seen even if no zip found to avoid endless retries if MB removed it
        except Exception as e:
            print("   Download failed for", sha, ":", e, file=sys.stderr)
        # be gentle on API
        time.sleep(SLEEP_BETWEEN)

if __name__ == "__main__":
    main()
