curl -s \
  -H "Auth-Key: YOUR-AUTH-KEY-HERE" \
  -d "query=get_file_type&file_type=pdf&limit=1000" \
  https://mb-api.abuse.ch/api/v1/ \
  | jq -r '.data[].sha256_hash' > pdf_sha256.txt
