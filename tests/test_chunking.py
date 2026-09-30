"""Behavioral tests for B1 provenance-preserving document chunks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from credit_agreement_extractor.chunking import (
    ChunkArtifact,
    InvalidChunkInputError,
    build_chunk_document,
    build_chunks,
)
from credit_agreement_extractor.conversion import ConversionArtifact
from credit_agreement_extractor.hierarchy import build_hierarchy_sidecar


SOURCE_SHA256 = "a" * 64
DOCLING_SHA256 = "b" * 64
HIERARCHY_SHA256 = "c" * 64


def _ref(item_id: str) -> dict[str, str]:
    return {"$ref": item_id}


def _text(
    index: int,
    text: str,
    *,
    orig: str | None = None,
    page: int | tuple[int, ...] | None = 1,
    label: str = "text",
    level: int | None = None,
    parent_id: str = "#/body",
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "self_ref": f"#/texts/{index}",
        "parent": _ref(parent_id),
        "children": [],
        "label": label,
        "text": text,
        "prov": (
            []
            if page is None
            else [
                {"page_no": page_number}
                for page_number in ((page,) if isinstance(page, int) else page)
            ]
        ),
    }
    if orig is not None:
        item["orig"] = orig
    if level is not None:
        item["level"] = level
    return item


def _table(
    index: int,
    rows: list[list[str]],
    *,
    page: int | tuple[int, ...] | None = 1,
    parent_id: str = "#/body",
) -> dict[str, Any]:
    grid = [[{"text": cell} for cell in row] for row in rows]
    return {
        "self_ref": f"#/tables/{index}",
        "parent": _ref(parent_id),
        "children": [],
        "label": "table",
        "prov": (
            []
            if page is None
            else [
                {"page_no": page_number}
                for page_number in ((page,) if isinstance(page, int) else page)
            ]
        ),
        "data": {"grid": grid},
    }


def _canonical(
    *,
    texts: list[dict[str, Any]] | None = None,
    tables: list[dict[str, Any]] | None = None,
    groups: list[dict[str, Any]] | None = None,
    body_children: list[str] | None = None,
) -> dict[str, Any]:
    text_items = texts or []
    table_items = tables or []
    group_items = groups or []
    children = body_children or [
        *(item["self_ref"] for item in text_items if item["parent"]["$ref"] == "#/body"),
        *(item["self_ref"] for item in table_items if item["parent"]["$ref"] == "#/body"),
    ]
    return {
        "body": {"self_ref": "#/body", "children": [_ref(item) for item in children]},
        "groups": group_items,
        "texts": text_items,
        "tables": table_items,
        "pictures": [],
        "form_items": [],
        "key_value_items": [],
    }


def _build(canonical: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    hierarchy = build_hierarchy_sidecar(canonical, source_sha256=SOURCE_SHA256)
    arguments = {
        "source_sha256": SOURCE_SHA256,
        "docling_json_sha256": DOCLING_SHA256,
        "hierarchy_json_sha256": HIERARCHY_SHA256,
    }
    arguments.update(overrides)
    return build_chunk_document(canonical, hierarchy, **arguments)


def _conversion_artifact(tmp_path: Path) -> ConversionArtifact:
    source_path = tmp_path / "agreement.pdf"
    source_path.write_bytes(b"%PDF-1.4\nexample\n%%EOF\n")
    output_directory = tmp_path / "converted" / SOURCE_SHA256
    output_directory.mkdir(parents=True)
    canonical = _canonical(
        texts=[
            _text(0, "Parties", label="section_header", level=1, page=1),
            _text(1, "Example Borrower, LLC", page=1),
            _text(2, "Interest", label="section_header", level=1, page=2),
            _text(3, "SOFR plus margin", page=2),
        ]
    )
    hierarchy = build_hierarchy_sidecar(canonical, source_sha256=SOURCE_SHA256)
    markdown_path = output_directory / "document.md"
    docling_path = output_directory / "document.docling.json"
    hierarchy_path = output_directory / "document.hierarchy.json"
    manifest_path = output_directory / "manifest.json"
    markdown_path.write_text("# Agreement\n", encoding="utf-8")
    docling_path.write_text(json.dumps(canonical), encoding="utf-8")
    hierarchy_path.write_text(json.dumps(hierarchy), encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "source": {"sha256": SOURCE_SHA256},
                "artifacts": {
                    "docling_json": docling_path.name,
                    "hierarchy_json": hierarchy_path.name,
                },
            }
        ),
        encoding="utf-8",
    )
    return ConversionArtifact(
        source_path=source_path,
        source_sha256=SOURCE_SHA256,
        source_format="pdf",
        output_directory=output_directory,
        markdown_path=markdown_path,
        docling_json_path=docling_path,
        hierarchy_json_path=hierarchy_path,
        manifest_path=manifest_path,
        cached=False,
    )


def test_retains_normalized_and_original_text_and_renders_original() -> None:
    result = _build(
        _canonical(texts=[_text(0, "Borrower", orig="(1) Borrower")])
    )

    item = result["chunks"][0]["items"][0]
    assert item["text"] == "Borrower"
    assert item["original_text"] == "(1) Borrower"
    assert result["chunks"][0]["content"] == "(1) Borrower"


def test_renders_table_grid_deterministically() -> None:
    result = _build(
        _canonical(tables=[_table(0, [["Name", "Amount"], ["A", "$10"]])])
    )

    assert result["chunks"][0]["content"] == "Name\tAmount\nA\t$10"


def test_rejects_hierarchy_for_another_source() -> None:
    canonical = _canonical(texts=[_text(0, "Borrower")])
    hierarchy = build_hierarchy_sidecar(canonical, source_sha256="wrong")

    with pytest.raises(InvalidChunkInputError, match="source SHA-256"):
        build_chunk_document(
            canonical,
            hierarchy,
            source_sha256=SOURCE_SHA256,
            docling_json_sha256=DOCLING_SHA256,
            hierarchy_json_sha256=HIERARCHY_SHA256,
        )


def test_rejects_duplicate_reading_order_item() -> None:
    canonical = _canonical(texts=[_text(0, "Borrower")])
    hierarchy = build_hierarchy_sidecar(canonical, source_sha256=SOURCE_SHA256)
    hierarchy["reading_order"].append("#/texts/0")

    with pytest.raises(InvalidChunkInputError, match="duplicate"):
        build_chunk_document(
            canonical,
            hierarchy,
            source_sha256=SOURCE_SHA256,
            docling_json_sha256=DOCLING_SHA256,
            hierarchy_json_sha256=HIERARCHY_SHA256,
        )


def test_rejects_unresolved_reading_order_item() -> None:
    canonical = _canonical(texts=[_text(0, "Borrower")])
    hierarchy = build_hierarchy_sidecar(canonical, source_sha256=SOURCE_SHA256)
    hierarchy["reading_order"] = ["#/texts/99"]

    with pytest.raises(InvalidChunkInputError, match="does not resolve"):
        build_chunk_document(
            canonical,
            hierarchy,
            source_sha256=SOURCE_SHA256,
            docling_json_sha256=DOCLING_SHA256,
            hierarchy_json_sha256=HIERARCHY_SHA256,
        )


def test_rejects_non_integer_hierarchy_pages() -> None:
    canonical = _canonical(texts=[_text(0, "Borrower")])
    hierarchy = build_hierarchy_sidecar(canonical, source_sha256=SOURCE_SHA256)
    hierarchy["items"]["#/texts/0"]["pages"] = ["1"]

    with pytest.raises(InvalidChunkInputError, match="page numbers"):
        build_chunk_document(
            canonical,
            hierarchy,
            source_sha256=SOURCE_SHA256,
            docling_json_sha256=DOCLING_SHA256,
            hierarchy_json_sha256=HIERARCHY_SHA256,
        )


def test_rejects_unresolved_hierarchy_container_reference() -> None:
    canonical = _canonical(texts=[_text(0, "Borrower")])
    hierarchy = build_hierarchy_sidecar(canonical, source_sha256=SOURCE_SHA256)
    hierarchy["items"]["#/texts/0"]["container_path"] = [
        "#/body",
        "#/groups/99",
    ]

    with pytest.raises(InvalidChunkInputError, match="container reference"):
        build_chunk_document(
            canonical,
            hierarchy,
            source_sha256=SOURCE_SHA256,
            docling_json_sha256=DOCLING_SHA256,
            hierarchy_json_sha256=HIERARCHY_SHA256,
        )


def test_rejects_unresolved_hierarchy_heading_reference() -> None:
    canonical = _canonical(
        texts=[
            _text(0, "Parties", label="section_header", level=1),
            _text(1, "Borrower"),
        ]
    )
    hierarchy = build_hierarchy_sidecar(canonical, source_sha256=SOURCE_SHA256)
    hierarchy["items"]["#/texts/1"]["heading_path"][0]["item_id"] = "#/texts/99"

    with pytest.raises(InvalidChunkInputError, match="heading reference"):
        build_chunk_document(
            canonical,
            hierarchy,
            source_sha256=SOURCE_SHA256,
            docling_json_sha256=DOCLING_SHA256,
            hierarchy_json_sha256=HIERARCHY_SHA256,
        )


def test_paged_content_starts_a_new_chunk_at_each_page() -> None:
    result = _build(
        _canonical(
            texts=[
                _text(0, "First", page=1),
                _text(1, "Second", page=1),
                _text(2, "Third", page=2),
            ]
        )
    )

    assert [chunk["item_ids"] for chunk in result["chunks"]] == [
        ["#/texts/0", "#/texts/1"],
        ["#/texts/2"],
    ]
    assert result["chunks"][0]["next_chunk_id"] == "chunk-000002"
    assert result["chunks"][1]["previous_chunk_id"] == "chunk-000001"


def test_oversized_page_splits_only_between_items() -> None:
    result = _build(
        _canonical(texts=[_text(0, "aaaa", page=1), _text(1, "bbbb", page=1)]),
        target_characters=5,
    )

    assert [chunk["item_ids"] for chunk in result["chunks"]] == [
        ["#/texts/0"],
        ["#/texts/1"],
    ]
    assert [chunk["content"] for chunk in result["chunks"]] == ["aaaa", "bbbb"]


def test_explicit_list_is_atomic_across_pages_and_target() -> None:
    group_id = "#/groups/0"
    canonical = _canonical(
        texts=[
            _text(0, "(a) first limb", page=1, label="list_item", parent_id=group_id),
            _text(1, "(b) second limb", page=2, label="list_item", parent_id=group_id),
        ],
        groups=[
            {
                "self_ref": group_id,
                "parent": _ref("#/body"),
                "children": [_ref("#/texts/0"), _ref("#/texts/1")],
                "label": "list",
                "name": "list",
            }
        ],
        body_children=[group_id],
    )

    result = _build(canonical, target_characters=10)

    assert len(result["chunks"]) == 1
    assert result["chunks"][0]["item_ids"] == ["#/texts/0", "#/texts/1"]
    assert result["chunks"][0]["pages"] == [1, 2]
    assert result["chunks"][0]["atomic_group_ids"] == [group_id]
    assert result["chunks"][0]["oversized_reason"] == "atomic_list"


def test_multi_page_table_remains_atomic() -> None:
    result = _build(
        _canonical(tables=[_table(0, [["a" * 20]], page=(1, 2))]),
        target_characters=5,
    )

    assert len(result["chunks"]) == 1
    assert result["chunks"][0]["item_ids"] == ["#/tables/0"]
    assert result["chunks"][0]["pages"] == [1, 2]
    assert result["chunks"][0]["oversized_reason"] == "atomic_item"


def test_page_less_items_attach_without_inventing_pages() -> None:
    result = _build(
        _canonical(
            texts=[
                _text(0, "Leading", page=None),
                _text(1, "Page one", page=1),
                _text(2, "Continuation", page=None),
                _text(3, "Page two", page=2),
            ]
        )
    )

    assert [chunk["item_ids"] for chunk in result["chunks"]] == [
        ["#/texts/0", "#/texts/1", "#/texts/2"],
        ["#/texts/3"],
    ]
    assert result["chunks"][0]["items"][0]["pages"] == []
    assert result["chunks"][0]["pages"] == [1]


def test_leading_page_less_item_stays_with_first_paged_chunk_when_oversized() -> None:
    result = _build(
        _canonical(
            texts=[
                _text(0, "long leading material", page=None),
                _text(1, "Page one", page=1),
            ]
        ),
        target_characters=5,
    )

    assert [chunk["item_ids"] for chunk in result["chunks"]] == [
        ["#/texts/0", "#/texts/1"]
    ]


def test_later_page_less_item_stays_with_preceding_oversized_atomic_item() -> None:
    result = _build(
        _canonical(
            texts=[
                _text(0, "oversized paged material", page=1),
                _text(1, "continuation without page", page=None),
                _text(2, "Page two", page=2),
            ]
        ),
        target_characters=5,
    )

    assert [chunk["item_ids"] for chunk in result["chunks"]] == [
        ["#/texts/0", "#/texts/1"],
        ["#/texts/2"],
    ]


def test_page_less_document_prefers_heading_boundaries() -> None:
    result = _build(
        _canonical(
            texts=[
                _text(0, "Parties", page=None, label="section_header", level=1),
                _text(1, "Borrower and lender", page=None),
                _text(2, "Interest", page=None, label="section_header", level=1),
                _text(3, "SOFR plus margin", page=None),
            ]
        ),
        target_characters=30,
    )

    assert [chunk["item_ids"] for chunk in result["chunks"]] == [
        ["#/texts/0", "#/texts/1"],
        ["#/texts/2", "#/texts/3"],
    ]
    assert all(chunk["pages"] == [] for chunk in result["chunks"])


def test_every_reading_order_item_occurs_exactly_once_and_in_order() -> None:
    result = _build(
        _canonical(
            texts=[
                _text(0, "First", page=1),
                _text(1, "Second", page=1),
                _text(2, "Third", page=2),
            ],
            tables=[_table(0, [["Fourth"]], page=2)],
            body_children=[
                "#/texts/0",
                "#/texts/1",
                "#/texts/2",
                "#/tables/0",
            ],
        )
    )

    flattened = [
        item_id for chunk in result["chunks"] for item_id in chunk["item_ids"]
    ]
    assert flattened == result["source_reading_order"]
    assert len(flattened) == len(set(flattened))


def test_build_chunks_persists_stage_b_artifact_and_reuses_valid_cache(
    tmp_path: Path,
) -> None:
    conversion = _conversion_artifact(tmp_path)
    output_root = tmp_path / "stage_b"

    first = build_chunks(conversion, output_root=output_root)
    first_mtime = first.chunks_json_path.stat().st_mtime_ns
    second = build_chunks(conversion, output_root=output_root)

    assert isinstance(first, ChunkArtifact)
    assert first.cached is False
    assert second.cached is True
    assert first.output_directory == output_root / SOURCE_SHA256
    assert first.chunks_json_path == first.output_directory / "document.chunks.json"
    assert second.chunks_json_path.stat().st_mtime_ns == first_mtime
    persisted = json.loads(first.chunks_json_path.read_text(encoding="utf-8"))
    assert persisted["status"] == "completed"
    assert persisted["source_sha256"] == SOURCE_SHA256
    assert persisted["chunking_profile"] == "page-first-v1-chars-12000"


def test_changed_stage_a_bytes_invalidate_chunk_cache(tmp_path: Path) -> None:
    conversion = _conversion_artifact(tmp_path)
    output_root = tmp_path / "stage_b"
    first = build_chunks(conversion, output_root=output_root)
    canonical = json.loads(conversion.docling_json_path.read_text(encoding="utf-8"))
    canonical["name"] = "same content, changed canonical bytes"
    conversion.docling_json_path.write_text(json.dumps(canonical), encoding="utf-8")

    second = build_chunks(conversion, output_root=output_root)

    assert first.cached is False
    assert second.cached is False


def test_different_target_does_not_reuse_chunk_cache(tmp_path: Path) -> None:
    conversion = _conversion_artifact(tmp_path)
    output_root = tmp_path / "stage_b"
    build_chunks(conversion, output_root=output_root)

    second = build_chunks(
        conversion,
        output_root=output_root,
        target_characters=50,
    )

    assert second.cached is False
    persisted = json.loads(second.chunks_json_path.read_text(encoding="utf-8"))
    assert persisted["chunking_profile"] == "page-first-v1-chars-50"


def test_broken_neighbor_link_invalidates_chunk_cache(tmp_path: Path) -> None:
    conversion = _conversion_artifact(tmp_path)
    output_root = tmp_path / "stage_b"
    first = build_chunks(conversion, output_root=output_root)
    persisted = json.loads(first.chunks_json_path.read_text(encoding="utf-8"))
    persisted["chunks"][0]["next_chunk_id"] = "chunk-999999"
    first.chunks_json_path.write_text(json.dumps(persisted), encoding="utf-8")

    second = build_chunks(conversion, output_root=output_root)

    assert second.cached is False
    repaired = json.loads(second.chunks_json_path.read_text(encoding="utf-8"))
    assert repaired["chunks"][0]["next_chunk_id"] == "chunk-000002"


def test_failed_rebuild_removes_stale_completed_chunk_artifact(
    tmp_path: Path,
) -> None:
    conversion = _conversion_artifact(tmp_path)
    output_root = tmp_path / "stage_b"
    first = build_chunks(conversion, output_root=output_root)
    conversion.hierarchy_json_path.write_text("{", encoding="utf-8")

    with pytest.raises(InvalidChunkInputError, match="valid JSON"):
        build_chunks(conversion, output_root=output_root)

    assert not first.chunks_json_path.exists()


def test_build_chunks_requires_completed_stage_a_manifest(tmp_path: Path) -> None:
    conversion = _conversion_artifact(tmp_path)
    conversion.manifest_path.write_text(
        json.dumps({"status": "incomplete"}), encoding="utf-8"
    )

    with pytest.raises(InvalidChunkInputError, match="completed Stage A"):
        build_chunks(conversion, output_root=tmp_path / "stage_b")
