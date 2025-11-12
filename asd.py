#!/usr/bin/env python3
"""
grabber_api_pdf.py
Fetch recent PDF samples from MalwareBazaar (no CLI, pure HTTP API), skip duplicates, download ZIPs.

Prereqs:
  pip install requests
Env:
  export MB_AUTH_KEY="YOUR_ABUSE_CH_API_KEY"   # required for downloads
Usage:
  python3 grabber_api_pdf.py
"""

import os, sys, time, json, pathlib, requests
from datetime import datetime

API_URL = "https://mb-api.abuse.ch/api/v1/"
STATE = pathlib.Path("~/.mb_seen_pdfs.txt").expanduser()
OUT_DIR = pathlib.Path("~/mb_downloads").expanduser()
LIMIT = int(os.getenv("MB_LIMIT", "200"))  # how many recent to consider

OUT_DIR.mkdir(parents=True, exist_ok=True)

def load_seen():
    if not STATE.exists():
        return set()
    return {line.strip() for line in STATE.read_text().splitlines() if line.strip()}

def append_seen(sha):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with STATE.open("a") as f:
        f.write(sha + "\n")

def api_post(payload, need_key=False, stream=False):
    headers = {}
    key = os.getenv("MB_AUTH_KEY", "")
    if need_key:
        if not key:
            print("ERROR: MB_AUTH_KEY not set — download calls require an API key.", file=sys.stderr)
            sys.exit(1)
        # Send key in multiple headers to cover all API variants
        headers["API-KEY"] = key
        headers["X-API-KEY"] = key
        headers["Authorization"] = f"Bearer {key}"
    r = requests.post(API_URL, data=payload, headers=headers, timeout=60, stream=stream)
    r.raise_for_status()
    return r


    r = requests.post(API_URL, data=payload, headers=headers, timeout=60, stream=stream)
    r.raise_for_status()
    return r

def fetch_recent_pdfs(limit=200):
    """
    Use 'get_file_type' to retrieve recent entries by file type.
    Many deployments accept 'selector=time' to bias recent.
    """
    payload = {
        "query": "get_file_type",
        "file_type": "pdf",
        "limit": str(limit),
        "selector": "time",
    }
    r = api_post(payload)
    try:
        data = r.json()
    except Exception:
        print("Server did not return JSON; raw head:", r.text[:400], file=sys.stderr)
        sys.exit(1)
    entries = data.get("data", [])
    # normalize timestamp and sort newest first
    def ts(x):
        # examples: '2025-11-01 06:52:29'
        s = (x.get("first_seen") or x.get("last_seen") or "").strip()
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").timestamp()
        except Exception:
            return 0.0
    entries.sort(key=ts, reverse=True)
    return entries

def download_zip_for_sha(sha):
    """
    Use 'get_file' to retrieve a password-protected ZIP for the sample.
    Writes a .zip into OUT_DIR and returns the path.
    """
    payload = {"query": "get_file", "sha256_hash": sha}
    r = api_post(payload, need_key=True, stream=True)
    # If API returns JSON error, try to show it
    ctype = r.headers.get("Content-Type", "")
    if "application/zip" not in ctype and "application/octet-stream" not in ctype:
        txt = r.text[:800]
        raise RuntimeError(f"Unexpected content-type ({ctype}). Server said: {txt}")
    # filename from header if present, else synthesize
    fname = None
    cd = r.headers.get("Content-Disposition", "")
    if "filename=" in cd:
        fname = cd.split("filename=", 1)[1].strip().strip('"')
    if not fname:
        fname = f"{sha}.zip"
    out_path = OUT_DIR / fname
    with out_path.open("wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
    return out_path

def main():
    print(f"State file: {STATE}")
    print(f"Output dir: {OUT_DIR}")
    seen = load_seen()
    print(f"Loaded {len(seen)} seen SHAs.")

    print("Fetching recent PDF entries…")
    items = fetch_recent_pdfs(LIMIT)
    print(f"API returned {len(items)} items.")

    new = []
    for it in items:
        sha = it.get("sha256_hash") or it.get("sha256")
        if not sha:
            continue
        if sha in seen:
            continue
        new.append(sha)

    if not new:
        print("No new PDF samples found. Done.")
        return

    print(f"Will download {len(new)} new samples (newest first).")
    for i, sha in enumerate(new, 1):
        try:
            print(f"[{i}/{len(new)}] downloading {sha} …")
            path = download_zip_for_sha(sha)
            print(f"   saved to {path}")
            append_seen(sha)
            time.sleep(float(os.getenv("MB_SLEEP", "0.5")))
        except Exception as e:
            print(f"   ERROR for {sha}: {e}", file=sys.stderr)

    print("Done. Recent files:")
    for p in sorted(OUT_DIR.glob("*.zip"), key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
        print(" -", p)

if __name__ == "__main__":
    main()

curl -X POST https://mb-api.abuse.ch/api/v1/ \
     -H "API-KEY: $MB_AUTH_KEY" \
     -d "query=get_recent"
