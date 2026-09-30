"""Build A10 hierarchy context from canonical Docling JSON.

The canonical Docling export remains the source of truth. This module creates a
small sidecar that points back to canonical item IDs; it does not rewrite,
summarize, reorder, or discard document content.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


class InvalidHierarchyInputError(ValueError):
    """Raised when canonical references cannot be traversed safely."""


@dataclass(frozen=True, slots=True)
class TraversedItem:
    """One canonical item plus the container ancestry found during traversal."""

    item_id: str
    item: Mapping[str, Any]
    parent_id: str
    container_path: tuple[str, ...]
    is_container: bool


@dataclass(frozen=True, slots=True)
class ObservedHeading:
    """Minimal heading facts needed for deterministic quality warnings."""

    item_id: str
    depth: int
    pages: tuple[int, ...]


_COLLECTION_ITEM_TYPES = {
    "groups": "group",
    "texts": "text",
    "tables": "table",
    "pictures": "picture",
    "form_items": "form_item",
    "key_value_items": "key_value_item",
}


def _index_canonical_items(
    canonical: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    """Index the root body and supported canonical collections by item ID."""
    body = canonical.get("body")
    if not isinstance(body, Mapping):
        raise InvalidHierarchyInputError("Canonical JSON must contain a body mapping.")
    if body.get("self_ref") != "#/body":
        raise InvalidHierarchyInputError(
            "Canonical body self_ref must equal '#/body'."
        )

    index: dict[str, Mapping[str, Any]] = {"#/body": body}
    for collection_name in _COLLECTION_ITEM_TYPES:
        collection = canonical.get(collection_name, [])
        if not isinstance(collection, Sequence) or isinstance(
            collection, (str, bytes, bytearray)
        ):
            raise InvalidHierarchyInputError(
                f"Canonical collection {collection_name!r} must be a sequence."
            )

        for position, item in enumerate(collection):
            if not isinstance(item, Mapping):
                raise InvalidHierarchyInputError(
                    f"Canonical item #/{collection_name}/{position} must be a mapping."
                )
            item_id = f"#/{collection_name}/{position}"
            if item.get("self_ref") != item_id:
                raise InvalidHierarchyInputError(
                    f"Canonical item {item_id} has conflicting self_ref "
                    f"{item.get('self_ref')!r}."
                )
            index[item_id] = item
    return index


def _child_references(item: Mapping[str, Any], *, item_id: str) -> Sequence[Any]:
    """Return a container's ordered child-reference records."""
    children = item.get("children", [])
    if not isinstance(children, Sequence) or isinstance(
        children, (str, bytes, bytearray)
    ):
        raise InvalidHierarchyInputError(
            f"Canonical item {item_id} must have a children sequence."
        )
    return children


def _walk_body_refs(
    index: Mapping[str, Mapping[str, Any]],
) -> Iterator[TraversedItem]:
    """Expand body/group references in canonical reading order."""

    def walk_container(
        container_id: str,
        container_path: tuple[str, ...],
        active_containers: frozenset[str],
    ) -> Iterator[TraversedItem]:
        container = index[container_id]
        for child_ref in _child_references(container, item_id=container_id):
            if not isinstance(child_ref, Mapping) or not isinstance(
                child_ref.get("$ref"), str
            ):
                raise InvalidHierarchyInputError(
                    f"Canonical item {container_id} has a malformed child reference."
                )

            child_id = child_ref["$ref"]
            child = index.get(child_id)
            if child is None:
                raise InvalidHierarchyInputError(
                    f"Canonical child reference does not resolve: {child_id}"
                )

            is_container = child_id.startswith("#/groups/")
            yield TraversedItem(
                item_id=child_id,
                item=child,
                parent_id=container_id,
                container_path=container_path,
                is_container=is_container,
            )

            if is_container:
                if child_id in active_containers:
                    raise InvalidHierarchyInputError(
                        f"Canonical group reference cycle includes {child_id}."
                    )
                yield from walk_container(
                    child_id,
                    (*container_path, child_id),
                    active_containers | {child_id},
                )

    yield from walk_container("#/body", ("#/body",), frozenset({"#/body"}))


def _canonical_pages(item: Mapping[str, Any]) -> list[int]:
    """Return unique, sorted positive page numbers from canonical provenance."""
    provenance = item.get("prov", [])
    if not isinstance(provenance, Sequence) or isinstance(
        provenance, (str, bytes, bytearray)
    ):
        return []

    pages = {
        page
        for record in provenance
        if isinstance(record, Mapping)
        and isinstance((page := record.get("page_no")), int)
        and not isinstance(page, bool)
        and page > 0
    }
    return sorted(pages)


def _item_type(item_id: str) -> str:
    """Translate a canonical collection name into a stable sidecar item type."""
    collection_name = item_id.split("/", maxsplit=2)[1]
    return _COLLECTION_ITEM_TYPES[collection_name]


def _heading_record(item_id: str, item: Mapping[str, Any]) -> dict[str, Any]:
    """Return the only source wording copied into the sidecar."""
    level = item.get("level")
    if not isinstance(level, int) or isinstance(level, bool) or level <= 0:
        raise InvalidHierarchyInputError(
            f"Section heading {item_id} must have a positive integer level."
        )
    text = item.get("text")
    return {
        "item_id": item_id,
        "depth": level,
        "text": text if isinstance(text, str) else "",
    }


def _warning_pages(*headings: ObservedHeading) -> list[int]:
    """Combine involved heading pages without fabricating missing provenance."""
    return sorted({page for heading in headings for page in heading.pages})


def _hierarchy_warnings(
    headings: Sequence[ObservedHeading],
) -> list[dict[str, Any]]:
    """Apply only the four warning rules frozen for the first A10 schema."""
    if not headings:
        return [
            {
                "code": "no_headings",
                "message": "No usable section headings were found.",
                "item_ids": [],
                "pages": [],
                "details": {},
            }
        ]

    warnings: list[dict[str, Any]] = []
    previous: ObservedHeading | None = None
    for heading in headings:
        if previous is None and heading.depth > 1:
            warnings.append(
                {
                    "code": "skipped_levels",
                    "message": (
                        f"Heading depth started at {heading.depth} instead of 1."
                    ),
                    "item_ids": [heading.item_id],
                    "pages": list(heading.pages),
                    "details": {"from_depth": 0, "to_depth": heading.depth},
                }
            )
        elif previous is not None and heading.depth > previous.depth + 1:
            warnings.append(
                {
                    "code": "skipped_levels",
                    "message": (
                        f"Heading depth jumped from {previous.depth} "
                        f"to {heading.depth}."
                    ),
                    "item_ids": [previous.item_id, heading.item_id],
                    "pages": _warning_pages(previous, heading),
                    "details": {
                        "from_depth": previous.depth,
                        "to_depth": heading.depth,
                    },
                }
            )

        previous_page = previous.pages[0] if previous and previous.pages else None
        heading_page = heading.pages[0] if heading.pages else None
        if (
            previous is not None
            and previous_page is not None
            and heading_page is not None
            and heading_page < previous_page
        ):
            warnings.append(
                {
                    "code": "non_monotonic_pages",
                    "message": (
                        f"Heading pages moved backward from {previous_page} "
                        f"to {heading_page}."
                    ),
                    "item_ids": [previous.item_id, heading.item_id],
                    "pages": _warning_pages(previous, heading),
                    "details": {
                        "from_page": previous_page,
                        "to_page": heading_page,
                    },
                }
            )
        previous = heading

    depths = {heading.depth for heading in headings}
    if len(headings) >= 2 and len(depths) == 1:
        depth = headings[0].depth
        warnings.append(
            {
                "code": "flat_levels",
                "message": (
                    f"All {len(headings)} section headings use depth {depth}."
                ),
                "item_ids": [heading.item_id for heading in headings],
                "pages": _warning_pages(*headings),
                "details": {"depth": depth, "heading_count": len(headings)},
            }
        )

    return warnings


def build_hierarchy_sidecar(
    canonical: Mapping[str, Any],
    *,
    source_sha256: str,
) -> dict[str, Any]:
    """Return deterministic hierarchy context keyed by canonical item IDs."""
    index = _index_canonical_items(canonical)
    reading_order: list[str] = []
    items: dict[str, dict[str, Any]] = {}
    active_headings: dict[int, dict[str, Any]] = {}
    observed_headings: list[ObservedHeading] = []

    for traversed in _walk_body_refs(index):
        item = traversed.item
        if item.get("label") == "section_header":
            heading = _heading_record(traversed.item_id, item)
            level = heading["depth"]
            observed_headings.append(
                ObservedHeading(
                    item_id=traversed.item_id,
                    depth=level,
                    pages=tuple(_canonical_pages(item)),
                )
            )
            active_headings = {
                depth: active
                for depth, active in active_headings.items()
                if depth < level
            }
            active_headings[level] = heading

        reading_order_index: int | None = None
        if not traversed.is_container:
            reading_order_index = len(reading_order)
            reading_order.append(traversed.item_id)

        items[traversed.item_id] = {
            "item_type": _item_type(traversed.item_id),
            "reading_order_index": reading_order_index,
            "parent_id": traversed.parent_id,
            "container_path": list(traversed.container_path),
            "pages": _canonical_pages(item),
            "heading_path": [
                active_headings[depth] for depth in sorted(active_headings)
            ],
        }

    return {
        "schema_version": 1,
        "source_sha256": source_sha256,
        "generator": {
            "name": "credit-agreement-parser-a10",
            "strategy": "docling-tree-plus-heading-stack",
        },
        "warnings": _hierarchy_warnings(observed_headings),
        "reading_order": reading_order,
        "items": items,
    }
