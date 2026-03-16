"""Tests for HTM -> PDF conversion helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "convert_htm_to_pdf.py"
spec = importlib.util.spec_from_file_location("convert_htm_to_pdf", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_prepare_html_for_pdf_injects_overflow_fix_css() -> None:
    html = "<html><head><title>T</title></head><body><table><tr><td>nowrap-token</td></tr></table></body></html>"

    normalized = module.prepare_html_for_pdf(html)

    assert "credit-agreement-parser print overflow fix" in normalized
    assert "@page" in normalized
    assert "table-layout: fixed" in normalized
    assert "overflow-wrap: anywhere" in normalized


def test_prepare_html_for_pdf_without_head_tag() -> None:
    html = "<html><body><div>Example</div></body></html>"

    normalized = module.prepare_html_for_pdf(html)

    assert "credit-agreement-parser print overflow fix" in normalized
    assert normalized.count("<style") >= 1
    assert "<div>Example</div>" in normalized
