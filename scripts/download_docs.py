"""Download credit agreement documents from CSV of URLs."""
import csv
import os
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlparse, unquote

OUTPUT_DIR = Path("/Users/ashrit/Desktop/Credit_Agreement_Parsing/raw_documents")
CSV_PATH = Path("/Users/ashrit/Desktop/Credit_Agreement_Parsing/corporate_credit_agreement_source_urls_50.csv")


def sanitize_filename(url: str, idx: int) -> str:
    """Generate a clean filename from URL, prefixed with index."""
    parsed = urlparse(url)
    basename = unquote(parsed.path.split("/")[-1])
    # Remove problematic characters
    basename = re.sub(r'[^\w\-.]', '_', basename)
    # Trim excessive length
    if len(basename) > 80:
        basename = basename[:80]
    # Ensure extension
    if not basename.lower().endswith(('.pdf', '.htm', '.html')):
        # Guess from URL
        if '.pdf' in url.lower():
            basename += '.pdf'
        elif '.htm' in url.lower():
            basename += '.htm'
        else:
            basename += '.htm'  # default for SEC filings
    return f"{idx:03d}_{basename}"


def download_file(url: str, filepath: Path, max_retries: int = 2) -> bool:
    """Download a single file with retries."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
    }
    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read()
                filepath.write_bytes(data)
                return True
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            if attempt < max_retries:
                time.sleep(2 * (attempt + 1))
            else:
                print(f"  FAILED after {max_retries + 1} attempts: {e}")
                return False
    return False


def main():
    urls = []
    with open(CSV_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row["url"].strip()
            if url:
                urls.append(url)

    print(f"Found {len(urls)} URLs to download\n")

    results = {"success": [], "failed": []}

    for idx, url in enumerate(urls, 1):
        filename = sanitize_filename(url, idx)
        filepath = OUTPUT_DIR / filename

        if filepath.exists():
            print(f"[{idx:02d}/49] SKIP (exists): {filename}")
            results["success"].append((idx, url, filename))
            continue

        print(f"[{idx:02d}/49] Downloading: {filename}")
        print(f"         URL: {url[:100]}...")

        if download_file(url, filepath):
            size_kb = filepath.stat().st_size / 1024
            print(f"         OK ({size_kb:.1f} KB)")
            results["success"].append((idx, url, filename))
        else:
            results["failed"].append((idx, url, filename))

        # Be polite to servers
        time.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"Downloaded: {len(results['success'])}/{len(urls)}")
    if results["failed"]:
        print(f"\nFailed downloads:")
        for idx, url, fname in results["failed"]:
            print(f"  [{idx:02d}] {url}")


if __name__ == "__main__":
    main()
