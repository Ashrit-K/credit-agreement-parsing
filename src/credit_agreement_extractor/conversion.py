"""Convert source agreements into durable, traceable intermediate artifacts.

Docling's structured JSON is the canonical conversion result. Markdown is a
derived, human-readable view that will also be convenient for later LLM calls.
Neither representation is written beside the source document: source files are
immutable and all generated data lives under a separate output root.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterator, Protocol


class InvalidDocumentInputError(ValueError):
    """Raised when a source path cannot be converted safely."""


class DoclingDocumentLike(Protocol):
    """Small portion of ``DoclingDocument`` used by the persistence layer."""

    def export_to_markdown(self) -> str:
        """Return the document's readable Markdown representation."""
        ...

    def export_to_dict(self) -> dict[str, Any]:
        """Return Docling's canonical, JSON-serializable representation."""
        ...


class ConversionResultLike(Protocol):
    """Match the ``document`` attribute on Docling's conversion result."""

    document: DoclingDocumentLike


class DocumentConverterLike(Protocol):
    """Allow unit tests to replace the comparatively heavy Docling runtime."""

    def convert(self, source_path: Path) -> ConversionResultLike:
        """Convert one normalized source document."""
        ...


@dataclass(frozen=True, slots=True)
class ConversionArtifact:
    """Paths and source identity produced by one conversion operation."""

    source_path: Path
    source_sha256: str
    source_format: str
    output_directory: Path
    markdown_path: Path
    docling_json_path: Path
    manifest_path: Path
    cached: bool


_SUPPORTED_SUFFIXES = {
    ".pdf": "pdf",
    ".html": "html",
    ".htm": "html",
}

# Bump this identifier whenever settings or serialization behavior changes in a
# way that should invalidate earlier artifacts. The source hash alone only says
# the input is identical; it does not say the conversion recipe is identical.
_CONVERSION_PROFILE = "docling-json-v2-rapidocr-en-heading-hierarchy"


def _validate_source_path(source_path: str | Path) -> tuple[Path, str]:
    """Return a usable source path and normalized format without changing it."""
    path = Path(source_path).expanduser()
    if not path.exists():
        raise InvalidDocumentInputError(f"Document path does not exist: {path}")
    if not path.is_file():
        raise InvalidDocumentInputError(
            f"Document path is not a regular file: {path}"
        )
    if path.stat().st_size == 0:
        raise InvalidDocumentInputError(f"Document file is empty: {path}")

    source_format = _SUPPORTED_SUFFIXES.get(path.suffix.lower())
    if source_format is None:
        supported = ", ".join(sorted(_SUPPORTED_SUFFIXES))
        raise InvalidDocumentInputError(
            f"Document must use one of these extensions: {supported}; got {path}"
        )
    return path, source_format


def _sha256(path: Path) -> str:
    """Fingerprint a source incrementally so very large agreements stay bounded."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _docling_version() -> str | None:
    """Record the converter version when installed without blocking test doubles."""
    try:
        return version("docling")
    except PackageNotFoundError:
        return None


def _artifact_paths(
    *,
    source_path: Path,
    source_sha256: str,
    source_format: str,
    output_root: Path,
    cached: bool,
) -> ConversionArtifact:
    """Build every path from one content fingerprint in a single place."""
    output_directory = output_root / source_sha256
    return ConversionArtifact(
        source_path=source_path,
        source_sha256=source_sha256,
        source_format=source_format,
        output_directory=output_directory,
        markdown_path=output_directory / "document.md",
        docling_json_path=output_directory / "document.docling.json",
        manifest_path=output_directory / "manifest.json",
        cached=cached,
    )


def _is_complete_cache(artifact: ConversionArtifact) -> bool:
    """Accept a cache hit only when its files and recorded source agree."""
    required_paths = (
        artifact.markdown_path,
        artifact.docling_json_path,
        artifact.manifest_path,
    )
    if not all(path.is_file() for path in required_paths):
        return False

    try:
        manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    return (
        manifest.get("status") == "completed"
        and manifest.get("source", {}).get("sha256") == artifact.source_sha256
        and manifest.get("conversion_profile") == _CONVERSION_PROFILE
    )


def _default_converter() -> DocumentConverterLike:
    """Load Docling lazily and keep PDF OCR local, explicit, and English-only."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        HeadingHierarchyOptions,
        PdfPipelineOptions,
        RapidOcrOptions,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pdf_options = PdfPipelineOptions(
        do_ocr=True,
        ocr_options=RapidOcrOptions(lang=["iso:en"]),
        heading_hierarchy_options=HeadingHierarchyOptions(enabled=True),
        generate_parsed_pages=True,
    )
    return DocumentConverter(
        # Restrict detection to the formats promised by our public function.
        # This reduces accidental behavior growth as Docling adds formats.
        allowed_formats=[InputFormat.PDF, InputFormat.HTML],
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
        },
    )


def _has_gzip_header(path: Path) -> bool:
    """Check the content signature because several SEC `.htm` files are gzip."""
    with path.open("rb") as source:
        return source.read(2) == b"\x1f\x8b"


@contextmanager
def _normalized_source(
    path: Path,
    *,
    source_format: str,
    temporary_root: Path,
) -> Iterator[tuple[Path, bool]]:
    """Yield plain HTML for gzip-wrapped filings, then remove the temporary copy.

    The normalized copy belongs to the conversion run, never to the preserved
    source corpus. Streaming decompression also avoids loading a long agreement
    into memory solely to unwrap its transport compression.
    """
    if source_format != "html" or not _has_gzip_header(path):
        yield path, False
        return

    with TemporaryDirectory(prefix=".normalizing-", dir=temporary_root) as directory:
        normalized_path = Path(directory) / "source.html"
        try:
            with gzip.open(path, "rb") as compressed, normalized_path.open(
                "wb"
            ) as output:
                shutil.copyfileobj(compressed, output)
        except (gzip.BadGzipFile, EOFError) as error:
            raise InvalidDocumentInputError(
                f"HTML file has a gzip signature but cannot be decompressed: {path}"
            ) from error
        yield normalized_path, True


def convert_document(
    source_path: str | Path,
    output_root: str | Path = Path("tmp/converted"),
    *,
    converter: DocumentConverterLike | None = None,
) -> ConversionArtifact:
    """Convert one PDF/HTML source and persist canonical and readable artifacts.

    A SHA-256 fingerprint identifies the source content. Repeating a conversion
    with identical bytes reuses a complete artifact directory, even if the
    caller used a different filename for the same source.
    """
    path, source_format = _validate_source_path(source_path)
    source_sha256 = _sha256(path)
    root = Path(output_root).expanduser()
    artifact = _artifact_paths(
        source_path=path,
        source_sha256=source_sha256,
        source_format=source_format,
        output_root=root,
        cached=False,
    )

    if _is_complete_cache(artifact):
        return replace(artifact, cached=True)

    artifact.output_directory.mkdir(parents=True, exist_ok=True)
    active_converter = converter if converter is not None else _default_converter()
    with _normalized_source(
        path,
        source_format=source_format,
        temporary_root=root,
    ) as (converter_source, gzip_normalized):
        conversion_result = active_converter.convert(converter_source)
        markdown = conversion_result.document.export_to_markdown()
        canonical = conversion_result.document.export_to_dict()

    artifact.markdown_path.write_text(markdown, encoding="utf-8")
    artifact.docling_json_path.write_text(
        json.dumps(canonical, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": 1,
        "conversion_profile": _CONVERSION_PROFILE,
        "status": "completed",
        "converted_at": datetime.now(UTC).isoformat(),
        "source": {
            "path": str(path),
            "name": path.name,
            "sha256": source_sha256,
            "format": source_format,
        },
        "converter": {
            "name": "docling",
            "version": _docling_version(),
        },
        "ocr": {
            # OCR belongs to the PDF pipeline. HTML is already text-bearing,
            # so marking it enabled there would incorrectly imply OCR ran.
            "enabled": source_format == "pdf",
            "engine": "rapidocr",
            "languages": ["iso:en"],
        },
        "heading_hierarchy": {
            # Built-in inference is currently configured only on the PDF
            # pipeline. A10 can still consume structure already present in a
            # canonical HTML export without claiming this PDF stage ran.
            "enabled": source_format == "pdf",
            "provider": "docling",
            "generate_parsed_pages": source_format == "pdf",
        },
        "gzip_normalized": gzip_normalized,
        "artifacts": {
            "markdown": artifact.markdown_path.name,
            "docling_json": artifact.docling_json_path.name,
        },
    }
    artifact.manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return artifact
