#!/bin/sh
set -e

echo "Downloading crawl_webkit_1.jsonl..."
wget "https://zenodo.org/records/22163943/files/crawl_webkit_1.jsonl?download=1" -O crawl_webkit_1.jsonl

echo "Downloading crawl_webkit_2.jsonl..."
wget "https://zenodo.org/records/22163943/files/crawl_webkit_2.jsonl?download=1" -O crawl_webkit_2.jsonl

echo "Downloading webprivacy-lists.tar.gz..."
wget "https://zenodo.org/records/22163943/files/webprivacy-lists.tar.gz?download=1" -O webprivacy-lists.tar.gz

echo "Extracting tar archive..."
tar -xzf webprivacy-lists.tar.gz 2>/dev/null

echo "Cleaning up..."
rm webprivacy-lists.tar.gz

echo "Verifying files..."
if [ ! -f "crawl_webkit_1.jsonl" ] || [ ! -f "crawl_webkit_2.jsonl" ]; then
    echo "Error: The JSONL files are missing from the directory." >&2
    exit 1
fi
if [ ! -d "webprivacy-lists" ]; then
    echo "Error: The extracted webprivacy-lists directory is missing." >&2
    exit 1
fi

echo "Success: All files downloaded successfully."