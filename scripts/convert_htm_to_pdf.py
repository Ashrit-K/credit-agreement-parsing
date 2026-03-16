"""Convert HTM files in raw_documents/htm to PDF in raw_documents/pdf."""

from __future__ import annotations

import argparse
import gzip
import re
import subprocess
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HTM_DIR = PROJECT_ROOT / "raw_documents" / "htm"
PDF_DIR = PROJECT_ROOT / "raw_documents" / "pdf"

# This CSS is injected into source HTM before conversion so very wide
# legacy SEC layouts wrap instead of clipping at the PDF page boundary.
PRINT_OVERFLOW_FIX_CSS = """
/* credit-agreement-parser print overflow fix */
@page { size: A3 landscape; margin: 0.35in; }
html, body {
  width: auto !important;
  max-width: 100% !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}
* { box-sizing: border-box; }
table, thead, tbody, tfoot, tr {
  width: 100% !important;
  max-width: 100% !important;
}
table { table-layout: fixed !important; border-collapse: collapse; }
th, td {
  white-space: normal !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
  max-width: 100% !important;
  vertical-align: top !important;
}
[nowrap], [style*="white-space:nowrap"], [style*="white-space: nowrap"] {
  white-space: normal !important;
}
pre, code {
  white-space: pre-wrap !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}
img, svg, canvas, object, embed, iframe {
  max-width: 100% !important;
  height: auto !important;
}
"""


def is_gzipped(filepath: Path) -> bool:
    with open(filepath, "rb") as f:
        return f.read(2) == b"\x1f\x8b"


def read_html_text(htm_path: Path) -> str:
    if is_gzipped(htm_path):
        raw_bytes = gzip.open(htm_path, "rb").read()
    else:
        raw_bytes = htm_path.read_bytes()
    return raw_bytes.decode("utf-8", errors="replace")


def prepare_html_for_pdf(html: str) -> str:
    """Inject print CSS to avoid horizontal clipping in converted PDFs."""
    if "credit-agreement-parser print overflow fix" in html:
        return html

    style_tag = f"<style>\n{PRINT_OVERFLOW_FIX_CSS}\n</style>"
    head_close = re.search(r"</head\s*>", html, flags=re.IGNORECASE)
    if head_close:
        return re.sub(r"</head\s*>", f"{style_tag}</head>", html, count=1, flags=re.IGNORECASE)

    html_open = re.search(r"<html[^>]*>", html, flags=re.IGNORECASE)
    if html_open:
        return re.sub(
            r"<html[^>]*>",
            lambda m: f"{m.group(0)}<head>{style_tag}</head>",
            html,
            count=1,
            flags=re.IGNORECASE,
        )

    return f"<head>{style_tag}</head>{html}"


def convert_one(htm_path: Path, force: bool = False) -> bool:
    pdf_name = htm_path.stem + ".pdf"
    pdf_path = PDF_DIR / pdf_name

    if pdf_path.exists() and not force:
        print(f"  SKIP (PDF exists): {pdf_name}")
        return True

    PDF_DIR.mkdir(parents=True, exist_ok=True)

    tmp_path: Path | None = None
    try:
        normalized_html = prepare_html_for_pdf(read_html_text(htm_path))

        with tempfile.NamedTemporaryFile(
            suffix=".htm", prefix=f"{htm_path.stem}_", mode="w", encoding="utf-8", delete=False
        ) as tmp:
            tmp.write(normalized_html)
            tmp_path = Path(tmp.name)

        result = subprocess.run(
            ["weasyprint", "--presentational-hints", str(tmp_path), str(pdf_path)],
            capture_output=True,
            text=True,
            timeout=180,
        )

        if result.returncode == 0 and pdf_path.exists() and pdf_path.stat().st_size > 0:
            size_kb = pdf_path.stat().st_size / 1024
            print(f"  OK ({size_kb:.0f} KB): {pdf_name}")
            return True

        print(f"  FAILED: {pdf_name} — {result.stderr[:240]}")
        pdf_path.unlink(missing_ok=True)
        return False

    except Exception as exc:
        print(f"  FAILED: {pdf_name} — {exc}")
        pdf_path.unlink(missing_ok=True)
        return False
    finally:
        if tmp_path:
            tmp_path.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert raw_documents/htm/*.htm into raw_documents/pdf/*.pdf"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate PDFs even if output file already exists.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    htm_files = sorted(HTM_DIR.glob("*.htm"))
    print(f"Found {len(htm_files)} HTM files to convert from {HTM_DIR}\n")

    success = 0
    failed = 0

    for htm in htm_files:
        print(f"[{htm.name}]")
        if convert_one(htm, force=args.force):
            success += 1
        else:
            failed += 1

    print(f"\n{'='*50}")
    print(f"Converted: {success}/{len(htm_files)}")
    if failed:
        print(f"Failed: {failed}")
    print(f"Total PDFs in {PDF_DIR}: {len(list(PDF_DIR.glob('*.pdf')))}")


if __name__ == "__main__":
    main()
