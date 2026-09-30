"""Unit tests for the pure A10 canonical-JSON hierarchy transformation.

These tests deliberately use small in-memory Docling-like mappings. A10 must be
independently reproducible without loading Docling, reading a PDF, or touching
the filesystem.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from credit_agreement_extractor.hierarchy import (
    InvalidHierarchyInputError,
    build_hierarchy_sidecar,
)


SOURCE_SHA256 = "a" * 64


def _ref(item_id: str) -> dict[str, str]:
    """Return the reference shape used by canonical Docling JSON."""
    return {"$ref": item_id}


def _text_item(
    index: int,
    text: str,
    *,
    label: str = "text",
    level: int | None = None,
    pages: tuple[int, ...] = (1,),
    parent_id: str = "#/body",
) -> dict[str, Any]:
    """Build one realistic canonical text item for focused unit tests."""
    item: dict[str, Any] = {
        "self_ref": f"#/texts/{index}",
        "parent": _ref(parent_id),
        "children": [],
        "label": label,
        "text": text,
        "prov": [{"page_no": page} for page in pages],
    }
    if level is not None:
        item["level"] = level
    return item


def _representative_canonical() -> dict[str, Any]:
    """Exercise body order, nested groups, heading replacement, and tables."""
    group_id = "#/groups/0"
    return {
        "body": {
            "self_ref": "#/body",
            "children": [
                _ref("#/texts/0"),
                _ref("#/texts/1"),
                _ref(group_id),
                _ref("#/texts/5"),
                _ref("#/texts/6"),
            ],
        },
        "groups": [
            {
                "self_ref": group_id,
                "parent": _ref("#/body"),
                "children": [
                    _ref("#/texts/2"),
                    _ref("#/texts/3"),
                    _ref("#/texts/4"),
                    _ref("#/tables/0"),
                ],
                "label": "section",
            }
        ],
        "texts": [
            _text_item(
                0,
                "ARTICLE I",
                label="section_header",
                level=1,
                pages=(1,),
            ),
            _text_item(1, "Opening paragraph", pages=(1,)),
            _text_item(
                2,
                "Definitions",
                label="section_header",
                level=2,
                pages=(2,),
                parent_id=group_id,
            ),
            _text_item(3, "Defined-term paragraph", pages=(2,), parent_id=group_id),
            _text_item(
                4,
                "Interest",
                label="section_header",
                level=2,
                pages=(3,),
                parent_id=group_id,
            ),
            _text_item(
                5,
                "ARTICLE II",
                label="section_header",
                level=1,
                pages=(4,),
            ),
            _text_item(6, "Closing paragraph", pages=(4,)),
        ],
        "tables": [
            {
                "self_ref": "#/tables/0",
                "parent": _ref(group_id),
                "children": [],
                "label": "table",
                "prov": [
                    {"page_no": 4},
                    {"page_no": 3},
                    {"page_no": 3},
                ],
                "data": {"grid": [["Do not copy table content"]]},
            }
        ],
        "pictures": [],
        "form_items": [],
        "key_value_items": [],
    }


def _canonical_with_headings(
    *headings: tuple[int, int],
) -> dict[str, Any]:
    """Build a flat body containing headings described by ``(level, page)``."""
    texts = [
        _text_item(
            index,
            f"Heading {index}",
            label="section_header",
            level=level,
            pages=(page,),
        )
        for index, (level, page) in enumerate(headings)
    ]
    if not texts:
        texts = [_text_item(0, "Only paragraph", pages=(1,))]
    return {
        "body": {
            "self_ref": "#/body",
            "children": [_ref(item["self_ref"]) for item in texts],
        },
        "groups": [],
        "texts": texts,
        "tables": [],
        "pictures": [],
        "form_items": [],
        "key_value_items": [],
    }


def test_builds_reading_order_and_preserves_container_ancestry() -> None:
    sidecar = build_hierarchy_sidecar(
        _representative_canonical(),
        source_sha256=SOURCE_SHA256,
    )

    assert sidecar["schema_version"] == 1
    assert sidecar["source_sha256"] == SOURCE_SHA256
    assert sidecar["generator"] == {
        "name": "credit-agreement-parser-a10",
        "strategy": "docling-tree-plus-heading-stack",
    }
    assert sidecar["reading_order"] == [
        "#/texts/0",
        "#/texts/1",
        "#/texts/2",
        "#/texts/3",
        "#/texts/4",
        "#/tables/0",
        "#/texts/5",
        "#/texts/6",
    ]
    assert sidecar["items"]["#/groups/0"] == {
        "item_type": "group",
        "reading_order_index": None,
        "parent_id": "#/body",
        "container_path": ["#/body"],
        "pages": [],
        "heading_path": [
            {"item_id": "#/texts/0", "depth": 1, "text": "ARTICLE I"}
        ],
    }
    assert sidecar["items"]["#/tables/0"]["parent_id"] == "#/groups/0"
    assert sidecar["items"]["#/tables/0"]["container_path"] == [
        "#/body",
        "#/groups/0",
    ]
    assert sidecar["items"]["#/tables/0"]["pages"] == [3, 4]


def test_builds_generic_heading_paths_and_replaces_equal_or_shallower_levels() -> None:
    sidecar = build_hierarchy_sidecar(
        _representative_canonical(),
        source_sha256=SOURCE_SHA256,
    )

    article_one = {"item_id": "#/texts/0", "depth": 1, "text": "ARTICLE I"}
    definitions = {"item_id": "#/texts/2", "depth": 2, "text": "Definitions"}
    interest = {"item_id": "#/texts/4", "depth": 2, "text": "Interest"}
    article_two = {"item_id": "#/texts/5", "depth": 1, "text": "ARTICLE II"}

    assert sidecar["items"]["#/texts/0"]["heading_path"] == [article_one]
    assert sidecar["items"]["#/texts/3"]["heading_path"] == [
        article_one,
        definitions,
    ]
    assert sidecar["items"]["#/texts/4"]["heading_path"] == [
        article_one,
        interest,
    ]
    assert sidecar["items"]["#/tables/0"]["heading_path"] == [
        article_one,
        interest,
    ]
    assert sidecar["items"]["#/texts/6"]["heading_path"] == [article_two]


def test_does_not_mutate_input_or_copy_substantive_leaf_content() -> None:
    canonical = _representative_canonical()
    before = copy.deepcopy(canonical)

    first = build_hierarchy_sidecar(canonical, source_sha256=SOURCE_SHA256)
    second = build_hierarchy_sidecar(canonical, source_sha256=SOURCE_SHA256)

    assert canonical == before
    assert first == second
    serialized = json.dumps(first)
    assert "Opening paragraph" not in serialized
    assert "Defined-term paragraph" not in serialized
    assert "Closing paragraph" not in serialized
    assert "Do not copy table content" not in serialized


def test_warns_when_no_headings_are_available() -> None:
    sidecar = build_hierarchy_sidecar(
        _canonical_with_headings(),
        source_sha256=SOURCE_SHA256,
    )

    assert sidecar["warnings"] == [
        {
            "code": "no_headings",
            "message": "No usable section headings were found.",
            "item_ids": [],
            "pages": [],
            "details": {},
        }
    ]


def test_warns_when_multiple_headings_all_use_one_level() -> None:
    sidecar = build_hierarchy_sidecar(
        _canonical_with_headings((1, 1), (1, 2)),
        source_sha256=SOURCE_SHA256,
    )

    assert sidecar["warnings"] == [
        {
            "code": "flat_levels",
            "message": "All 2 section headings use depth 1.",
            "item_ids": ["#/texts/0", "#/texts/1"],
            "pages": [1, 2],
            "details": {"depth": 1, "heading_count": 2},
        }
    ]


def test_warns_in_reading_order_for_initial_and_later_skipped_levels() -> None:
    sidecar = build_hierarchy_sidecar(
        _canonical_with_headings((2, 1), (4, 2)),
        source_sha256=SOURCE_SHA256,
    )

    assert sidecar["warnings"] == [
        {
            "code": "skipped_levels",
            "message": "Heading depth started at 2 instead of 1.",
            "item_ids": ["#/texts/0"],
            "pages": [1],
            "details": {"from_depth": 0, "to_depth": 2},
        },
        {
            "code": "skipped_levels",
            "message": "Heading depth jumped from 2 to 4.",
            "item_ids": ["#/texts/0", "#/texts/1"],
            "pages": [1, 2],
            "details": {"from_depth": 2, "to_depth": 4},
        },
    ]


def test_warns_when_consecutive_heading_pages_move_backward() -> None:
    sidecar = build_hierarchy_sidecar(
        _canonical_with_headings((1, 5), (2, 4)),
        source_sha256=SOURCE_SHA256,
    )

    assert sidecar["warnings"] == [
        {
            "code": "non_monotonic_pages",
            "message": "Heading pages moved backward from 5 to 4.",
            "item_ids": ["#/texts/0", "#/texts/1"],
            "pages": [4, 5],
            "details": {"from_page": 5, "to_page": 4},
        }
    ]


def test_warning_codes_are_limited_to_the_frozen_taxonomy() -> None:
    allowed_codes = {
        "no_headings",
        "flat_levels",
        "skipped_levels",
        "non_monotonic_pages",
    }

    sidecars = [
        build_hierarchy_sidecar(
            _canonical_with_headings(),
            source_sha256=SOURCE_SHA256,
        ),
        build_hierarchy_sidecar(
            _canonical_with_headings((1, 1), (1, 2)),
            source_sha256=SOURCE_SHA256,
        ),
        build_hierarchy_sidecar(
            _canonical_with_headings((2, 5), (4, 4)),
            source_sha256=SOURCE_SHA256,
        ),
    ]

    assert {
        warning["code"]
        for sidecar in sidecars
        for warning in sidecar["warnings"]
    } <= allowed_codes


def test_rejects_unresolved_child_reference() -> None:
    canonical = _representative_canonical()
    canonical["body"]["children"].append(_ref("#/texts/99"))

    with pytest.raises(InvalidHierarchyInputError, match="does not resolve"):
        build_hierarchy_sidecar(canonical, source_sha256=SOURCE_SHA256)


def test_rejects_group_reference_cycle() -> None:
    canonical = _representative_canonical()
    canonical["groups"][0]["children"] = [_ref("#/groups/0")]

    with pytest.raises(InvalidHierarchyInputError, match="cycle"):
        build_hierarchy_sidecar(canonical, source_sha256=SOURCE_SHA256)


@pytest.mark.parametrize("bad_level", [None, True, 0, -1, 1.5, "2"])
def test_rejects_malformed_heading_level(bad_level: object) -> None:
    canonical = _representative_canonical()
    heading = canonical["texts"][0]
    if bad_level is None:
        heading.pop("level")
    else:
        heading["level"] = bad_level

    with pytest.raises(InvalidHierarchyInputError, match="positive integer level"):
        build_hierarchy_sidecar(canonical, source_sha256=SOURCE_SHA256)


def test_rejects_self_ref_that_conflicts_with_collection_position() -> None:
    canonical = _representative_canonical()
    canonical["texts"][0]["self_ref"] = "#/texts/99"

    with pytest.raises(InvalidHierarchyInputError, match="self_ref"):
        build_hierarchy_sidecar(canonical, source_sha256=SOURCE_SHA256)
