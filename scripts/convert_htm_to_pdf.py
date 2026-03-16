"""Convert HTM files in raw_documents to PDF using weasyprint."""
import gzip
import subprocess
import tempfile
from pathlib import Path

RAW_DIR = Path("/Users/ashrit/Desktop/Credit_Agreement_Parsing/raw_documents")


def is_gzipped(filepath: Path) -> bool:
    with open(filepath, "rb") as f:
        return f.read(2) == b"\x1f\x8b"


def convert_one(htm_path: Path) -> bool:
    pdf_name = htm_path.stem + ".pdf"
    pdf_path = htm_path.parent / pdf_name

    if pdf_path.exists():
        print(f"  SKIP (PDF exists): {pdf_name}")
        return True

    try:
        # Decompress if gzipped
        if is_gzipped(htm_path):
            with gzip.open(htm_path, "rb") as f:
                html_bytes = f.read()
            # Write decompressed to temp file
            tmp = tempfile.NamedTemporaryFile(suffix=".htm", delete=False)
            tmp.write(html_bytes)
            tmp.close()
            source = tmp.name
        else:
            source = str(htm_path)

        result = subprocess.run(
            ["weasyprint", source, str(pdf_path)],
            capture_output=True, text=True, timeout=120
        )

        if pdf_path.exists() and pdf_path.stat().st_size > 0:
            size_kb = pdf_path.stat().st_size / 1024
            print(f"  OK ({size_kb:.0f} KB): {pdf_name}")
            return True
        else:
            print(f"  FAILED: {pdf_name} — {result.stderr[:200]}")
            return False

    except Exception as e:
        print(f"  FAILED: {pdf_name} — {e}")
        pdf_path.unlink(missing_ok=True)
        return False


def main():
    htm_files = sorted(RAW_DIR.glob("*.htm"))
    print(f"Found {len(htm_files)} HTM files to convert\n")

    success = 0
    failed = 0

    for htm in htm_files:
        print(f"[{htm.name}]")
        if convert_one(htm):
            success += 1
        else:
            failed += 1

    print(f"\n{'='*50}")
    print(f"Converted: {success}/{len(htm_files)}")
    if failed:
        print(f"Failed: {failed}")

    # Count total PDFs now
    total_pdfs = len(list(RAW_DIR.glob("*.pdf")))
    print(f"Total PDFs in raw_documents: {total_pdfs}")


if __name__ == "__main__":
    main()
