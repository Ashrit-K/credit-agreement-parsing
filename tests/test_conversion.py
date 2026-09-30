"""Behavioral tests for durable document-conversion artifacts.

The tests inject a tiny converter double so they exercise our filesystem,
fingerprinting, and cache contract without loading Docling models.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import credit_agreement_extractor.conversion as conversion_module
from credit_agreement_extractor.conversion import (
    InvalidDocumentInputError,
    _default_converter,
    convert_document,
)
from credit_agreement_extractor.hierarchy import InvalidHierarchyInputError


class FakeDoclingDocument:
    """Minimal stand-in for the two Docling export methods we consume."""

    def export_to_markdown(self) -> str:
        return "# Credit Agreement\n\nExample Borrower, LLC"

    def export_to_dict(self) -> dict[str, object]:
        return {
            "name": "agreement",
            "body": {
                "self_ref": "#/body",
                "children": [
                    {"$ref": "#/texts/0"},
                    {"$ref": "#/texts/1"},
                ],
            },
            "groups": [],
            "texts": [
                {
                    "self_ref": "#/texts/0",
                    "parent": {"$ref": "#/body"},
                    "children": [],
                    "label": "section_header",
                    "level": 1,
                    "text": "Credit Agreement",
                    "prov": [{"page_no": 1}],
                },
                {
                    "self_ref": "#/texts/1",
                    "parent": {"$ref": "#/body"},
                    "children": [],
                    "label": "text",
                    "text": "Example Borrower, LLC",
                    "prov": [
                        {
                            "page_no": 1,
                            "bbox": {"l": 72.0, "t": 100.0, "r": 300.0, "b": 120.0},
                            "charspan": [0, 21],
                        }
                    ],
                }
            ],
            "tables": [],
            "pictures": [],
            "form_items": [],
            "key_value_items": [],
        }


class FakeConversionResult:
    """Match Docling's ``ConversionResult.document`` boundary."""

    document = FakeDoclingDocument()


class RecordingConverter:
    """Record which normalized source path reached the converter."""

    def __init__(self) -> None:
        self.received_paths: list[Path] = []
        self.received_bytes: list[bytes] = []

    def convert(self, source_path: Path) -> FakeConversionResult:
        self.received_paths.append(source_path)
        self.received_bytes.append(source_path.read_bytes())
        return FakeConversionResult()


class FailingConverter:
    """Prove a valid cache entry bypasses conversion entirely."""

    def convert(self, source_path: Path) -> FakeConversionResult:
        raise AssertionError(f"converter should not be called for cache hit: {source_path}")


def test_pdf_conversion_persists_canonical_and_derived_artifacts(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "agreement.pdf"
    source_path.write_bytes(b"%PDF-1.4\nexample\n%%EOF\n")
    output_root = tmp_path / "converted"
    converter = RecordingConverter()

    artifact = convert_document(source_path, output_root, converter=converter)

    assert converter.received_paths == [source_path]
    assert artifact.output_directory == output_root / artifact.source_sha256
    assert artifact.markdown_path.read_text(encoding="utf-8").startswith(
        "# Credit Agreement"
    )

    canonical = json.loads(artifact.docling_json_path.read_text(encoding="utf-8"))
    assert canonical == FakeDoclingDocument().export_to_dict()
    assert canonical["texts"][1]["self_ref"] == "#/texts/1"
    assert canonical["texts"][1]["prov"][0] == {
        "page_no": 1,
        "bbox": {"l": 72.0, "t": 100.0, "r": 300.0, "b": 120.0},
        "charspan": [0, 21],
    }

    hierarchy = json.loads(
        artifact.hierarchy_json_path.read_text(encoding="utf-8")
    )
    assert hierarchy["schema_version"] == 1
    assert hierarchy["source_sha256"] == artifact.source_sha256
    assert hierarchy["reading_order"] == ["#/texts/0", "#/texts/1"]
    assert hierarchy["items"]["#/texts/1"]["heading_path"] == [
        {"item_id": "#/texts/0", "depth": 1, "text": "Credit Agreement"}
    ]

    manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))
    assert (
        manifest["conversion_profile"]
        == "docling-json-v3-rapidocr-en-hierarchy-sidecar-v1"
    )
    assert manifest["source"]["sha256"] == artifact.source_sha256
    assert manifest["source"]["format"] == "pdf"
    assert manifest["artifacts"] == {
        "markdown": "document.md",
        "docling_json": "document.docling.json",
        "hierarchy_json": "document.hierarchy.json",
    }
    assert manifest["hierarchy_sidecar"] == {
        "schema_version": 1,
        "warning_count": 0,
        "warning_codes": [],
    }
    assert manifest["status"] == "completed"
    assert all(
        path.is_file()
        for path in (
            artifact.markdown_path,
            artifact.docling_json_path,
            artifact.hierarchy_json_path,
            artifact.manifest_path,
        )
    )
    assert manifest["ocr"] == {
        "enabled": True,
        "engine": "rapidocr",
        "languages": ["iso:en"],
    }
    assert manifest["heading_hierarchy"] == {
        "enabled": True,
        "provider": "docling",
        "generate_parsed_pages": True,
    }
    assert artifact.cached is False


def test_matching_complete_artifact_directory_is_reused(tmp_path: Path) -> None:
    source_path = tmp_path / "agreement.htm"
    source_path.write_text("<html><body>Agreement</body></html>", encoding="utf-8")
    output_root = tmp_path / "converted"

    first = convert_document(source_path, output_root, converter=RecordingConverter())
    modification_times = {
        path: path.stat().st_mtime_ns
        for path in (
            first.markdown_path,
            first.docling_json_path,
            first.hierarchy_json_path,
            first.manifest_path,
        )
    }

    second = convert_document(source_path, output_root, converter=FailingConverter())

    assert second.cached is True
    assert second.source_sha256 == first.source_sha256
    assert {
        path: path.stat().st_mtime_ns for path in modification_times
    } == modification_times


def test_changed_conversion_profile_invalidates_cached_artifacts(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "agreement.htm"
    source_path.write_text("<html><body>Agreement</body></html>", encoding="utf-8")
    output_root = tmp_path / "converted"
    first = convert_document(source_path, output_root, converter=RecordingConverter())
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    manifest["conversion_profile"] = "obsolete-profile"
    first.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    replacement_converter = RecordingConverter()

    second = convert_document(
        source_path,
        output_root,
        converter=replacement_converter,
    )

    assert second.cached is False
    assert replacement_converter.received_paths == [source_path]


@pytest.mark.parametrize(
    "tamper",
    [
        pytest.param(lambda path: path.unlink(), id="missing"),
        pytest.param(
            lambda path: path.write_text("{", encoding="utf-8"),
            id="malformed",
        ),
        pytest.param(
            lambda path: _rewrite_hierarchy(path, source_sha256="wrong-sha"),
            id="wrong-source-sha",
        ),
        pytest.param(
            lambda path: _rewrite_hierarchy(path, schema_version=99),
            id="unsupported-schema",
        ),
    ],
)
def test_invalid_hierarchy_sidecar_invalidates_cache(
    tmp_path: Path,
    tamper: Callable[[Path], object],
) -> None:
    source_path = tmp_path / "agreement.pdf"
    source_path.write_bytes(b"%PDF-1.4\nexample\n%%EOF\n")
    output_root = tmp_path / "converted"
    first = convert_document(source_path, output_root, converter=RecordingConverter())
    tamper(first.hierarchy_json_path)
    replacement_converter = RecordingConverter()

    second = convert_document(
        source_path,
        output_root,
        converter=replacement_converter,
    )

    assert second.cached is False
    assert replacement_converter.received_paths == [source_path]


def test_hierarchy_failure_removes_stale_completed_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "agreement.pdf"
    source_path.write_bytes(b"%PDF-1.4\nexample\n%%EOF\n")
    output_root = tmp_path / "converted"
    first = convert_document(source_path, output_root, converter=RecordingConverter())
    first.hierarchy_json_path.unlink()

    def fail_hierarchy(
        canonical: dict[str, Any], *, source_sha256: str
    ) -> dict[str, Any]:
        raise InvalidHierarchyInputError("broken canonical hierarchy")

    monkeypatch.setattr(
        conversion_module,
        "build_hierarchy_sidecar",
        fail_hierarchy,
    )

    with pytest.raises(InvalidHierarchyInputError, match="broken canonical"):
        convert_document(
            source_path,
            output_root,
            converter=RecordingConverter(),
        )

    assert not first.manifest_path.exists()


def test_gzip_wrapped_html_is_normalized_without_changing_source(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "filing.htm"
    html = b"<html><body><p>Credit Agreement</p></body></html>"
    compressed_html = gzip.compress(html)
    source_path.write_bytes(compressed_html)
    converter = RecordingConverter()

    artifact = convert_document(
        source_path,
        tmp_path / "converted",
        converter=converter,
    )

    normalized_path = converter.received_paths[0]
    assert normalized_path.suffix == ".html"
    assert converter.received_bytes == [html]
    assert not normalized_path.exists()
    assert source_path.read_bytes() == compressed_html

    manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))
    assert manifest["gzip_normalized"] is True
    assert manifest["ocr"]["enabled"] is False
    assert manifest["heading_hierarchy"] == {
        "enabled": False,
        "provider": "docling",
        "generate_parsed_pages": False,
    }


def test_default_docling_converter_uses_local_english_rapidocr() -> None:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import RapidOcrOptions

    converter = _default_converter()
    pdf_options = converter.format_to_options[InputFormat.PDF].pipeline_options

    assert converter.allowed_formats == [InputFormat.PDF, InputFormat.HTML]
    assert pdf_options.do_ocr is True
    assert isinstance(pdf_options.ocr_options, RapidOcrOptions)
    # Docling canonicalizes ``iso:en`` to its explicit Latin-script tag.
    assert pdf_options.ocr_options.lang == ["iso:en-Latn"]
    assert pdf_options.generate_parsed_pages is True
    assert pdf_options.heading_hierarchy_options.enabled is True


def test_broken_gzip_html_reports_a_document_input_error(tmp_path: Path) -> None:
    source_path = tmp_path / "broken.htm"
    source_path.write_bytes(b"\x1f\x8bnot-a-valid-gzip-stream")

    with pytest.raises(InvalidDocumentInputError, match="gzip"):
        convert_document(
            source_path,
            tmp_path / "converted",
            converter=RecordingConverter(),
        )


@pytest.mark.parametrize(
    ("source_factory", "message"),
    [
        (lambda root: root / "missing.pdf", "does not exist"),
        (lambda root: root, "regular file"),
        (lambda root: _write_empty(root / "empty.pdf"), "empty"),
        (lambda root: _write_text(root / "agreement.txt"), "extensions"),
    ],
)
def test_invalid_document_paths_are_rejected(
    tmp_path: Path,
    source_factory: Callable[[Path], Path],
    message: str,
) -> None:
    with pytest.raises(InvalidDocumentInputError, match=message):
        convert_document(
            source_factory(tmp_path),
            tmp_path / "converted",
            converter=RecordingConverter(),
        )


def _write_empty(path: Path) -> Path:
    """Create an empty file while returning its path for parametrized tests."""
    path.touch()
    return path


def _write_text(path: Path) -> Path:
    """Create a non-empty unsupported file for extension validation."""
    path.write_text("not a supported source", encoding="utf-8")
    return path


def _rewrite_hierarchy(path: Path, **updates: object) -> None:
    """Rewrite selected top-level sidecar fields for cache-validation tests."""
    sidecar = json.loads(path.read_text(encoding="utf-8"))
    sidecar.update(updates)
    path.write_text(json.dumps(sidecar), encoding="utf-8")
