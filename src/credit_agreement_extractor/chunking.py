"""Build B1 provenance-preserving chunks from completed Stage A artifacts.

The canonical Docling JSON remains the source of truth. This module copies only
the source wording and structural references needed by downstream topic
classification; full layout provenance remains resolvable through item IDs.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class InvalidChunkInputError(ValueError):
    """Raised when Stage A artifacts cannot produce trustworthy B1 chunks."""


@dataclass(frozen=True, slots=True)
class ChunkArtifact:
    """Identity and path for one persisted B1 chunk artifact."""

    source_sha256: str
    output_directory: Path
    chunks_json_path: Path
    schema_version: int
    chunking_profile: str
    cached: bool


@dataclass(frozen=True, slots=True)
class _AtomicUnit:
    """One indivisible B1 unit made from a leaf or explicit Docling list."""

    item_ids: tuple[str, ...]
    atomic_group_ids: tuple[str, ...]
    pages: tuple[int, ...]
    items: tuple[dict[str, Any], ...]
    content: str
    starts_heading: bool


_CHUNK_SCHEMA_VERSION = 1
_CHUNKING_PROFILE = "page-first-v1"
_DEFAULT_TARGET_CHARACTERS = 12_000

_COLLECTION_ITEM_TYPES = {
    "groups": "group",
    "texts": "text",
    "tables": "table",
    "pictures": "picture",
    "form_items": "form_item",
    "key_value_items": "key_value_item",
}


def _is_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def _chunking_profile(target_characters: int) -> str:
    return f"{_CHUNKING_PROFILE}-chars-{target_characters}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _index_canonical_items(
    canonical: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    body = canonical.get("body")
    if not isinstance(body, Mapping) or body.get("self_ref") != "#/body":
        raise InvalidChunkInputError(
            "Canonical JSON must contain body self_ref '#/body'."
        )

    index: dict[str, Mapping[str, Any]] = {"#/body": body}
    for collection_name in _COLLECTION_ITEM_TYPES:
        collection = canonical.get(collection_name, [])
        if not _is_sequence(collection):
            raise InvalidChunkInputError(
                f"Canonical collection {collection_name!r} must be a sequence."
            )
        for position, item in enumerate(collection):
            item_id = f"#/{collection_name}/{position}"
            if not isinstance(item, Mapping) or item.get("self_ref") != item_id:
                raise InvalidChunkInputError(
                    f"Canonical item {item_id} has an invalid self_ref."
                )
            index[item_id] = item
    return index


def _validate_group_references(
    index: Mapping[str, Mapping[str, Any]],
) -> None:
    def visit(group_id: str, active: frozenset[str]) -> None:
        group = index[group_id]
        children = group.get("children", [])
        if not _is_sequence(children):
            raise InvalidChunkInputError(
                f"Canonical group {group_id} must have a children sequence."
            )
        for child in children:
            if not isinstance(child, Mapping) or not isinstance(
                child.get("$ref"), str
            ):
                raise InvalidChunkInputError(
                    f"Canonical group {group_id} has a malformed child reference."
                )
            child_id = child["$ref"]
            if child_id not in index:
                raise InvalidChunkInputError(
                    f"Canonical group reference does not resolve: {child_id}"
                )
            if child_id.startswith("#/groups/"):
                if child_id in active:
                    raise InvalidChunkInputError(
                        f"Canonical group reference cycle includes {child_id}."
                    )
                visit(child_id, active | {child_id})

    for item_id in index:
        if item_id.startswith("#/groups/"):
            visit(item_id, frozenset({item_id}))


def _validated_reading_order(
    hierarchy: Mapping[str, Any],
    *,
    source_sha256: str,
    index: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    if hierarchy.get("schema_version") != 1:
        raise InvalidChunkInputError("Hierarchy schema version must equal 1.")
    if hierarchy.get("source_sha256") != source_sha256:
        raise InvalidChunkInputError("Hierarchy source SHA-256 does not match B1 input.")

    hierarchy_items = hierarchy.get("items")
    reading_order = hierarchy.get("reading_order")
    if not isinstance(hierarchy_items, Mapping) or not _is_sequence(reading_order):
        raise InvalidChunkInputError(
            "Hierarchy must contain item mappings and a reading-order sequence."
        )

    ordered: list[str] = []
    seen: set[str] = set()
    for item_id in reading_order:
        if not isinstance(item_id, str):
            raise InvalidChunkInputError("Hierarchy reading-order IDs must be strings.")
        if item_id in seen:
            raise InvalidChunkInputError(
                f"Hierarchy reading order contains duplicate item ID: {item_id}"
            )
        if item_id not in index or item_id.startswith("#/groups/"):
            raise InvalidChunkInputError(
                f"Hierarchy reading-order item does not resolve to a leaf: {item_id}"
            )
        metadata = hierarchy_items.get(item_id)
        if not isinstance(metadata, Mapping):
            raise InvalidChunkInputError(
                f"Hierarchy metadata does not resolve for item: {item_id}"
            )
        seen.add(item_id)
        ordered.append(item_id)
    return ordered


def _item_type(item_id: str) -> str:
    collection_name = item_id.split("/", maxsplit=2)[1]
    return _COLLECTION_ITEM_TYPES[collection_name]


def _clean_cell(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\t", " ").splitlines()).strip()


def _render_table(item: Mapping[str, Any], *, item_id: str) -> str:
    data = item.get("data")
    grid = data.get("grid") if isinstance(data, Mapping) else None
    if not _is_sequence(grid):
        return ""

    rows: list[str] = []
    for row in grid:
        if not _is_sequence(row):
            raise InvalidChunkInputError(f"Table {item_id} has a malformed grid row.")
        cells = [
            _clean_cell(cell.get("text")) if isinstance(cell, Mapping) else ""
            for cell in row
        ]
        rows.append("\t".join(cells).rstrip())
    return "\n".join(rows).rstrip()


def _render_item(item_id: str, item: Mapping[str, Any]) -> str:
    if item_id.startswith("#/tables/"):
        return _render_table(item, item_id=item_id)
    original = item.get("orig")
    if isinstance(original, str) and original.strip():
        return original
    text = item.get("text")
    return text if isinstance(text, str) else ""


def _item_record(
    item_id: str,
    item: Mapping[str, Any],
    metadata: Mapping[str, Any],
    *,
    index: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    pages = metadata.get("pages", [])
    heading_path = metadata.get("heading_path", [])
    container_path = metadata.get("container_path", [])
    if not _is_sequence(pages) or not _is_sequence(heading_path) or not _is_sequence(
        container_path
    ):
        raise InvalidChunkInputError(
            f"Hierarchy metadata has malformed context for item: {item_id}"
        )
    if any(
        not isinstance(page, int) or isinstance(page, bool) or page <= 0
        for page in pages
    ):
        raise InvalidChunkInputError(
            f"Hierarchy page numbers must be positive integers for item: {item_id}"
        )
    parent_id = metadata.get("parent_id")
    if not isinstance(parent_id, str) or parent_id not in index:
        raise InvalidChunkInputError(
            f"Hierarchy parent reference does not resolve for item: {item_id}"
        )
    for heading in heading_path:
        if not isinstance(heading, Mapping):
            raise InvalidChunkInputError(
                f"Hierarchy heading path is malformed for item: {item_id}"
            )
        heading_id = heading.get("item_id")
        heading_item = index.get(heading_id) if isinstance(heading_id, str) else None
        if heading_item is None or heading_item.get("label") != "section_header":
            raise InvalidChunkInputError(
                f"Hierarchy heading reference does not resolve: {heading_id}"
            )

    text = item.get("text")
    original = item.get("orig")
    label = item.get("label")
    item_type = (
        label
        if item_id.startswith("#/texts/") and isinstance(label, str)
        else _item_type(item_id)
    )
    return {
        "item_id": item_id,
        "item_type": item_type,
        "text": text if isinstance(text, str) else None,
        "original_text": original if isinstance(original, str) else None,
        "pages": list(pages),
        "heading_path": list(heading_path),
        "parent_id": parent_id,
        "container_path": list(container_path),
    }


def _explicit_list_groups(
    metadata: Mapping[str, Any],
    index: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    container_path = metadata.get("container_path", [])
    if not _is_sequence(container_path):
        raise InvalidChunkInputError("Hierarchy container path must be a sequence.")
    groups: list[str] = []
    for container_id in container_path:
        if not isinstance(container_id, str):
            raise InvalidChunkInputError("Hierarchy container IDs must be strings.")
        container = index.get(container_id)
        if container is None or not (
            container_id == "#/body" or container_id.startswith("#/groups/")
        ):
            raise InvalidChunkInputError(
                f"Hierarchy container reference does not resolve: {container_id}"
            )
        if (
            container_id.startswith("#/groups/")
            and container.get("label") == "list"
        ):
            groups.append(container_id)
    return tuple(groups)


def _unit_content(renderings: Sequence[str]) -> str:
    return "\n".join(rendering for rendering in renderings if rendering)


def _build_atomic_units(
    reading_order: Sequence[str],
    *,
    index: Mapping[str, Mapping[str, Any]],
    hierarchy_items: Mapping[str, Any],
) -> list[_AtomicUnit]:
    units: list[_AtomicUnit] = []
    current_key: str | None = None
    current_ids: list[str] = []
    closed_lists: set[str] = set()

    def finish_current() -> None:
        nonlocal current_key, current_ids
        if not current_ids:
            return
        records = [
            _item_record(
                item_id,
                index[item_id],
                hierarchy_items[item_id],
                index=index,
            )
            for item_id in current_ids
        ]
        list_groups: list[str] = []
        for item_id in current_ids:
            for group_id in _explicit_list_groups(
                hierarchy_items[item_id], index
            ):
                if group_id not in list_groups:
                    list_groups.append(group_id)
        renderings = [_render_item(item_id, index[item_id]) for item_id in current_ids]
        pages = sorted({page for record in records for page in record["pages"]})
        first_item = index[current_ids[0]]
        units.append(
            _AtomicUnit(
                item_ids=tuple(current_ids),
                atomic_group_ids=tuple(list_groups),
                pages=tuple(pages),
                items=tuple(records),
                content=_unit_content(renderings),
                starts_heading=first_item.get("label") == "section_header",
            )
        )
        if current_key and current_key.startswith("#/groups/"):
            closed_lists.add(current_key)
        current_key = None
        current_ids = []

    for item_id in reading_order:
        list_groups = _explicit_list_groups(hierarchy_items[item_id], index)
        unit_key = list_groups[0] if list_groups else item_id
        if current_key == unit_key:
            current_ids.append(item_id)
            continue
        finish_current()
        if unit_key.startswith("#/groups/") and unit_key in closed_lists:
            raise InvalidChunkInputError(
                f"Explicit list group is not contiguous in reading order: {unit_key}"
            )
        current_key = unit_key
        current_ids = [item_id]
    finish_current()
    return units


def _combined_content_length(units: Sequence[_AtomicUnit]) -> int:
    return len(_unit_content([unit.content for unit in units]))


def _split_units_to_target(
    units: Sequence[_AtomicUnit],
    *,
    target_characters: int,
) -> list[list[_AtomicUnit]]:
    chunks: list[list[_AtomicUnit]] = []
    current: list[_AtomicUnit] = []
    for unit in units:
        if current and _combined_content_length([*current, unit]) > target_characters:
            chunks.append(current)
            current = []
        current.append(unit)
        if len(unit.content) > target_characters:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


def _partition_paged_units(
    units: Sequence[_AtomicUnit],
    *,
    target_characters: int,
) -> list[list[_AtomicUnit]]:
    chunks: list[list[_AtomicUnit]] = []
    current: list[_AtomicUnit] = []
    page_anchor: int | None = None

    for unit in units:
        unit_anchor = unit.pages[0] if unit.pages else None
        if unit_anchor is not None:
            if page_anchor is None:
                # Leading page-less items belong to the first paged chunk even
                # when their combined rendering exceeds the ordinary target.
                page_anchor = unit_anchor
            elif unit_anchor != page_anchor:
                if current:
                    chunks.append(current)
                current = []
                page_anchor = unit_anchor
            elif current and _combined_content_length(
                [*current, unit]
            ) > target_characters:
                chunks.append(current)
                current = []
        current.append(unit)
    if current:
        chunks.append(current)
    return chunks


def _partition_page_less_units(
    units: Sequence[_AtomicUnit],
    *,
    target_characters: int,
) -> list[list[_AtomicUnit]]:
    blocks: list[list[_AtomicUnit]] = []
    current_block: list[_AtomicUnit] = []
    for unit in units:
        if unit.starts_heading and current_block:
            blocks.append(current_block)
            current_block = []
        current_block.append(unit)
    if current_block:
        blocks.append(current_block)

    chunks: list[list[_AtomicUnit]] = []
    current_chunk: list[_AtomicUnit] = []
    for block in blocks:
        if _combined_content_length(block) > target_characters:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
            chunks.extend(
                _split_units_to_target(
                    block,
                    target_characters=target_characters,
                )
            )
            continue
        if (
            current_chunk
            and _combined_content_length([*current_chunk, *block])
            > target_characters
        ):
            chunks.append(current_chunk)
            current_chunk = []
        current_chunk.extend(block)
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def _chunk_record(
    units: Sequence[_AtomicUnit],
    *,
    sequence_index: int,
    chunk_count: int,
    target_characters: int,
) -> dict[str, Any]:
    item_ids = [item_id for unit in units for item_id in unit.item_ids]
    items = [item for unit in units for item in unit.items]
    content = _unit_content([unit.content for unit in units])
    atomic_group_ids = list(
        dict.fromkeys(
            group_id for unit in units for group_id in unit.atomic_group_ids
        )
    )
    pages = sorted({page for unit in units for page in unit.pages})
    chunk_number = sequence_index + 1
    oversized_reason: str | None = None
    if len(content) > target_characters:
        oversized_reason = "atomic_list" if atomic_group_ids else "atomic_item"
    return {
        "chunk_id": f"chunk-{chunk_number:06d}",
        "sequence_index": sequence_index,
        "pages": pages,
        "previous_chunk_id": (
            f"chunk-{chunk_number - 1:06d}" if sequence_index > 0 else None
        ),
        "next_chunk_id": (
            f"chunk-{chunk_number + 1:06d}"
            if sequence_index + 1 < chunk_count
            else None
        ),
        "item_ids": item_ids,
        "atomic_group_ids": atomic_group_ids,
        "character_count": len(content),
        "oversized_reason": oversized_reason,
        "items": items,
        "content": content,
    }


def build_chunk_document(
    canonical: Mapping[str, Any],
    hierarchy: Mapping[str, Any],
    *,
    source_sha256: str,
    docling_json_sha256: str,
    hierarchy_json_sha256: str,
    target_characters: int = _DEFAULT_TARGET_CHARACTERS,
) -> dict[str, Any]:
    """Return schema-versioned B1 chunks without filesystem access."""
    if target_characters <= 0:
        raise InvalidChunkInputError("Target characters must be positive.")
    index = _index_canonical_items(canonical)
    _validate_group_references(index)
    reading_order = _validated_reading_order(
        hierarchy,
        source_sha256=source_sha256,
        index=index,
    )
    hierarchy_items = hierarchy["items"]

    units = _build_atomic_units(
        reading_order,
        index=index,
        hierarchy_items=hierarchy_items,
    )
    if any(unit.pages for unit in units):
        chunk_units = _partition_paged_units(
            units,
            target_characters=target_characters,
        )
    else:
        chunk_units = _partition_page_less_units(
            units,
            target_characters=target_characters,
        )
    chunks = [
        _chunk_record(
            units_for_chunk,
            sequence_index=index,
            chunk_count=len(chunk_units),
            target_characters=target_characters,
        )
        for index, units_for_chunk in enumerate(chunk_units)
    ]
    flattened = [
        item_id for chunk in chunks for item_id in chunk["item_ids"]
    ]
    if flattened != reading_order or len(flattened) != len(set(flattened)):
        raise InvalidChunkInputError(
            "Chunk construction dropped, duplicated, or reordered source items."
        )
    return {
        "schema_version": _CHUNK_SCHEMA_VERSION,
        "status": "completed",
        "source_sha256": source_sha256,
        "chunking_profile": _chunking_profile(target_characters),
        "inputs": {
            "docling_json_sha256": docling_json_sha256,
            "hierarchy_json_sha256": hierarchy_json_sha256,
        },
        "generator": {
            "name": "credit-agreement-parser-b1",
            "target_characters": target_characters,
        },
        "source_reading_order": reading_order,
        "chunks": chunks,
    }


def _load_json_mapping(path: Path, *, description: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InvalidChunkInputError(
            f"{description} must contain valid JSON: {path}"
        ) from error
    if not isinstance(value, Mapping):
        raise InvalidChunkInputError(f"{description} must contain a JSON object.")
    return value


def _is_complete_chunk_data(
    value: Mapping[str, Any],
    *,
    source_sha256: str,
    docling_json_sha256: str,
    hierarchy_json_sha256: str,
    chunking_profile: str,
) -> bool:
    inputs = value.get("inputs")
    chunks = value.get("chunks")
    reading_order = value.get("source_reading_order")
    if not isinstance(inputs, Mapping) or not _is_sequence(chunks) or not _is_sequence(
        reading_order
    ):
        return False
    flattened: list[str] = []
    chunk_count = len(chunks)
    for sequence_index, chunk in enumerate(chunks):
        if not isinstance(chunk, Mapping):
            return False
        chunk_number = sequence_index + 1
        item_ids = chunk.get("item_ids")
        items = chunk.get("items")
        content = chunk.get("content")
        if (
            not isinstance(item_ids, list)
            or not all(isinstance(item_id, str) for item_id in item_ids)
            or not isinstance(items, list)
            or len(items) != len(item_ids)
            or not isinstance(content, str)
            or chunk.get("character_count") != len(content)
            or chunk.get("chunk_id") != f"chunk-{chunk_number:06d}"
            or chunk.get("sequence_index") != sequence_index
            or chunk.get("previous_chunk_id")
            != (f"chunk-{chunk_number - 1:06d}" if sequence_index else None)
            or chunk.get("next_chunk_id")
            != (
                f"chunk-{chunk_number + 1:06d}"
                if sequence_index + 1 < chunk_count
                else None
            )
        ):
            return False
        flattened.extend(item_ids)
    return (
        value.get("schema_version") == _CHUNK_SCHEMA_VERSION
        and value.get("status") == "completed"
        and value.get("source_sha256") == source_sha256
        and value.get("chunking_profile") == chunking_profile
        and inputs.get("docling_json_sha256") == docling_json_sha256
        and inputs.get("hierarchy_json_sha256") == hierarchy_json_sha256
        and flattened == list(reading_order)
        and len(flattened) == len(set(flattened))
    )


def _artifact_paths(
    *,
    source_sha256: str,
    output_root: Path,
    chunking_profile: str,
    cached: bool,
) -> ChunkArtifact:
    output_directory = output_root / source_sha256
    return ChunkArtifact(
        source_sha256=source_sha256,
        output_directory=output_directory,
        chunks_json_path=output_directory / "document.chunks.json",
        schema_version=_CHUNK_SCHEMA_VERSION,
        chunking_profile=chunking_profile,
        cached=cached,
    )


def build_chunks(
    conversion_artifact: Any,
    output_root: str | Path = Path("tmp/stage_b"),
    *,
    target_characters: int = _DEFAULT_TARGET_CHARACTERS,
) -> ChunkArtifact:
    """Persist or reuse B1 chunks for a completed Stage A artifact."""
    if target_characters <= 0:
        raise InvalidChunkInputError("Target characters must be positive.")

    required_paths = (
        conversion_artifact.markdown_path,
        conversion_artifact.docling_json_path,
        conversion_artifact.hierarchy_json_path,
        conversion_artifact.manifest_path,
    )
    if not all(isinstance(path, Path) and path.is_file() for path in required_paths):
        raise InvalidChunkInputError(
            "B1 requires a completed Stage A artifact with all four files."
        )
    manifest = _load_json_mapping(
        conversion_artifact.manifest_path,
        description="Stage A manifest",
    )
    if (
        manifest.get("status") != "completed"
        or manifest.get("source", {}).get("sha256")
        != conversion_artifact.source_sha256
    ):
        raise InvalidChunkInputError(
            "B1 requires a completed Stage A manifest for the same source."
        )

    docling_json_sha256 = _sha256_file(conversion_artifact.docling_json_path)
    hierarchy_json_sha256 = _sha256_file(conversion_artifact.hierarchy_json_path)
    profile = _chunking_profile(target_characters)
    artifact = _artifact_paths(
        source_sha256=conversion_artifact.source_sha256,
        output_root=Path(output_root).expanduser(),
        chunking_profile=profile,
        cached=False,
    )

    if artifact.chunks_json_path.is_file():
        try:
            cached_data = _load_json_mapping(
                artifact.chunks_json_path,
                description="B1 chunk artifact",
            )
        except InvalidChunkInputError:
            cached_data = {}
        if _is_complete_chunk_data(
            cached_data,
            source_sha256=artifact.source_sha256,
            docling_json_sha256=docling_json_sha256,
            hierarchy_json_sha256=hierarchy_json_sha256,
            chunking_profile=profile,
        ):
            return ChunkArtifact(
                source_sha256=artifact.source_sha256,
                output_directory=artifact.output_directory,
                chunks_json_path=artifact.chunks_json_path,
                schema_version=artifact.schema_version,
                chunking_profile=artifact.chunking_profile,
                cached=True,
            )

    artifact.output_directory.mkdir(parents=True, exist_ok=True)
    artifact.chunks_json_path.unlink(missing_ok=True)
    temporary_path = artifact.chunks_json_path.with_suffix(".json.tmp")
    temporary_path.unlink(missing_ok=True)
    try:
        canonical = _load_json_mapping(
            conversion_artifact.docling_json_path,
            description="Canonical Docling artifact",
        )
        hierarchy = _load_json_mapping(
            conversion_artifact.hierarchy_json_path,
            description="Hierarchy sidecar",
        )
        document = build_chunk_document(
            canonical,
            hierarchy,
            source_sha256=conversion_artifact.source_sha256,
            docling_json_sha256=docling_json_sha256,
            hierarchy_json_sha256=hierarchy_json_sha256,
            target_characters=target_characters,
        )
        temporary_path.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        persisted = _load_json_mapping(
            temporary_path,
            description="Temporary B1 chunk artifact",
        )
        if not _is_complete_chunk_data(
            persisted,
            source_sha256=artifact.source_sha256,
            docling_json_sha256=docling_json_sha256,
            hierarchy_json_sha256=hierarchy_json_sha256,
            chunking_profile=profile,
        ):
            raise InvalidChunkInputError(
                "Temporary B1 chunk artifact failed completion validation."
            )
        temporary_path.replace(artifact.chunks_json_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        artifact.chunks_json_path.unlink(missing_ok=True)
        raise
    return artifact
