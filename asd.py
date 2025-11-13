os.makedirs(download_dir, exist_ok=True)

with open(hash_list_path, "r") as fileout:
    for line in fileout:
        sha256 = line.strip()
        if not sha256:
            continue

        # ask MalwareBazaar if this hash exists
        response = bazaar.query_hash(sha256)
        if response.get("query_status") != "ok":
            print(f"[!] {sha256} not found: {response.get('query_status')}")
            continue

        try:
            # download the file content (ZIP, password "infected")
            file_content = bazaar.download_file(sha256)

            out_path = os.path.join(download_dir, f"{sha256}.zip")
            with open(out_path, "wb") as f:
                f.write(file_content)

            print(f"[+] Downloaded {sha256} -> {out_path}")
        except Exception as e:
            print(f"[!] Failed to download {sha256}: {e}")
