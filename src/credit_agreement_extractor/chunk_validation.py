"""Lossless B1 validation."""
import re
from typing import Any, Mapping

class InvalidTopicInputError(ValueError):
    """B1 evidence cannot support citations."""

def _validate_document(document: Mapping[str, Any]) -> None:
    if isinstance(document, Mapping) and 'annotations' in document:
        raise InvalidTopicInputError('Human annotation files are not pipeline evidence.')
    if not isinstance(document, Mapping) or document.get("schema_version") != 1 or document.get("status") != "completed":
        raise InvalidTopicInputError("B2 requires a completed B1 schema-version-1 document.")
    source = document.get("source_sha256")
    if not isinstance(source, str) or not re.fullmatch(r"[0-9a-f]{64}", source):
        raise InvalidTopicInputError("B1 source SHA-256 is invalid.")
    chunks = document.get("chunks")
    order = document.get("source_reading_order")
    if not isinstance(chunks, list) or not isinstance(order, list):
        raise InvalidTopicInputError("B1 chunks and reading order must be lists.")
    chunk_ids, observed = set(), []
    for chunk in chunks:
        if not isinstance(chunk, Mapping) or not isinstance(chunk.get("chunk_id"), str):
            raise InvalidTopicInputError("B1 chunk must have a string ID.")
        if chunk["chunk_id"] in chunk_ids:
            raise InvalidTopicInputError("Duplicate B1 chunk ID.")
        chunk_ids.add(chunk["chunk_id"])
        items, ids = chunk.get("items"), chunk.get("item_ids")
        if not isinstance(items, list) or not isinstance(ids, list) or not isinstance(chunk.get("content"), str):
            raise InvalidTopicInputError("B1 chunk evidence is malformed.")
        if any(not isinstance(i, Mapping) or not isinstance(i.get("item_id"), str) for i in items):
            raise InvalidTopicInputError("B1 item reference is malformed.")
        if [i["item_id"] for i in items] != ids:
            raise InvalidTopicInputError("B1 item IDs disagree with item records.")
        observed.extend(ids)
    if any(not isinstance(i, str) for i in order) or observed != order or len(set(observed)) != len(observed):
        raise InvalidTopicInputError("B1 source coverage is duplicated, missing, or reordered.")
    known = set(order)
    for chunk in chunks:
        for item in chunk["items"]:
            headings = item.get("heading_path", [])
            if not isinstance(headings, list):
                raise InvalidTopicInputError("B1 heading path must be a list.")
            for heading in headings:
                if not isinstance(heading, Mapping) or heading.get("item_id") not in known or not isinstance(heading.get("text"), str):
                    raise InvalidTopicInputError("B1 heading citation does not resolve.")
