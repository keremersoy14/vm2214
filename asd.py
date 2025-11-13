from malwarebazaar.api import Bazaar
from requests.exceptions import JSONDecodeError  # from requests
import os

bazaar = Bazaar("your_api_key_here")

hash_list_path = "/home/kali/Desktop/pdf_sha256.txt"
download_dir   = "/home/kali/Desktop/bazaar_samples"
os.makedirs(download_dir, exist_ok=True)

with open(hash_list_path, "r") as fileout:
    for line in fileout:
        sha256 = line.strip()
        if not sha256:
            continue

        try:
            response = bazaar.query_hash(sha256)
        except JSONDecodeError:
            print(f"[!] Non-JSON response for {sha256} (rate limit / server hiccup). Skipping.")
            continue
        except Exception as e:
            print(f"[!] Error querying {sha256}: {e}")
            continue

        if response.get("query_status") != "ok":
            print(f"[!] {sha256} not found: {response.get('query_status')}")
            continue

        try:
            file_content = bazaar.download_file(sha256)
            out_path = os.path.join(download_dir, f"{sha256}.zip")
            with open(out_path, "wb") as f:
                f.write(file_content)
            print(f"[+] Downloaded {sha256} -> {out_path}")
        except Exception as e:
            print(f"[!] Failed to download {sha256}: {e}")
