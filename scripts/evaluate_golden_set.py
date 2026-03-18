#!/usr/bin/env python3
"""Run parser evaluation across curated golden-set PDFs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluation.golden_set_eval import (
    evaluate_manifest,
    format_compact_table,
    load_expected_labels,
    write_evaluation_csv,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate parser output on golden-set documents.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("raw_documents/golden_set/golden_set_manifest.json"),
        help="Path to golden-set manifest JSON.",
    )
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=Path("raw_documents/golden_set/pdf"),
        help="Directory containing golden-set PDF files.",
    )
    parser.add_argument(
        "--csv-out",
        type=Path,
        default=Path("output/golden_set/golden_set_eval.csv"),
        help="Where to save CSV report.",
    )
    parser.add_argument(
        "--expected-labels",
        type=Path,
        default=Path("raw_documents/golden_set/expected_outputs.json"),
        help="Optional human-labeled expected outputs for exact mismatch checks.",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Skip CSV output and only print the terminal table.",
    )
    parser.add_argument(
        "--fail-on-anomaly",
        action="store_true",
        help="Exit non-zero if any anomalies/errors are present.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    expected_labels = None
    if args.expected_labels.exists():
        expected_labels = load_expected_labels(args.expected_labels)
    rows = evaluate_manifest(
        manifest_path=args.manifest,
        pdf_dir=args.pdf_dir,
        expected_labels=expected_labels,
    )

    print(format_compact_table(rows))

    error_rows = [row for row in rows if row.status == "error"]
    anomaly_rows = [row for row in rows if row.anomalies]
    print()
    print(
        f"Summary: docs={len(rows)}, "
        f"errors={len(error_rows)}, "
        f"docs_with_anomalies={len(anomaly_rows)}"
    )

    if not args.no_csv:
        write_evaluation_csv(rows, args.csv_out)
        print(f"CSV saved to: {args.csv_out}")

    if args.fail_on_anomaly and (error_rows or anomaly_rows):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
