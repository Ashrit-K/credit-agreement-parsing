"""B2 provisional topic guesses with auditable, unscored matching evidence."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping

from .chunking import ChunkArtifact
from .topic_taxonomy import CONTEXT_RULES, PARENT_TOPICS, RULES_VERSION, TAXONOMY_VERSION, VOCABULARY
from .tracing import traced


class InvalidTopicInputError(ValueError):
    """B1 evidence is malformed or cannot support reliable citations."""


@dataclass(frozen=True, slots=True)
class TopicSignalsArtifact:
    """Location and identity of the provisional B2 output."""
    source_sha256: str
    topic_signals_json_path: Path
    taxonomy_version: str
    rules_version: str


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    # Whitespace and dash spelling variants match without changing source text;
    # regex spans therefore still retrieve the exact wording in the artifact.
    words = re.split(r"[\s\-]+", phrase)
    separator = r"[\s\-\u2010-\u2014]+"
    return re.compile(r"(?<!\w)" + separator.join(re.escape(w) for w in words) + r"(?!\w)", re.IGNORECASE)


def _rules():
    for topic, phrases in VOCABULARY.items():
        for phrase in phrases:
            slug = re.sub(r"[^a-z0-9]+", "_", phrase.lower()).strip("_")
            yield topic, f"{topic}.{slug}", _phrase_pattern(phrase)
    # Restrict wildcard prefixes to words on one line. Punctuation or a new
    # paragraph ends the phrase; there is no unrestricted regex '.*' wildcard.
    yield "facility_and_commitment_terms", "facility_and_commitment_terms.wildcard", re.compile(
        r"(?<!\w)(?:[\w'-]+[ \t]+){0,6}(?:facility|loan)(?!\w)", re.IGNORECASE
    )


_RULES = tuple(_rules())


def _validate_document(document: Mapping[str, Any]) -> None:
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


def _evidence_sources(chunk):
    # Keep normalized/original views individually attributable, then scan joined
    # content for table renderings and phrases spanning neighboring items.
    for item in chunk["items"]:
        seen_text = set()
        for field in ("original_text", "text"):
            text = item.get(field)
            if isinstance(text, str) and text and text not in seen_text:
                seen_text.add(text)
                yield field, [item["item_id"]], text
        for heading in item.get("heading_path", []):
            yield "heading", [heading["item_id"]], heading["text"]
    if chunk["content"]:
        yield "chunk_content", list(chunk["item_ids"]), chunk["content"]


def classify_chunk_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return provisional labels for every chunk, preserving input and order.

    Every match counts as an initial guess. Rule provenance explains the guess;
    B3 will decide whether it survives reflection against the source evidence.
    """
    _validate_document(document)
    classifications = []
    for chunk in document["chunks"]:
        signals, seen, topics = [], set(), set()

        def record(topic, rule_id, source_kind, ids, matched_text):
            key = (rule_id, source_kind, tuple(ids), matched_text)
            if key in seen:
                return
            seen.add(key)
            signals.append({"topic": topic, "rule_id": rule_id, "source_kind": source_kind,
                            "item_ids": ids, "matched_text": matched_text})
            topics.add(topic)
            if topic in PARENT_TOPICS:
                topics.add(PARENT_TOPICS[topic])

        for source_kind, ids, text in _evidence_sources(chunk):
            for topic, rule_id, pattern in _RULES:
                # One occurrence per rule/source is sufficient; do not inflate
                # output by enumerating every repeated Borrower or Lender.
                match = pattern.search(text)
                if match:
                    record(topic, rule_id, source_kind, ids, match.group())
            for topic, name, left, right in CONTEXT_RULES:
                for anchor in re.finditer(left, text, re.IGNORECASE):
                    start, end = max(0, anchor.start() - 120), min(len(text), anchor.end() + 120)
                    counterpart = re.search(right, text[start:end], re.IGNORECASE)
                    if counterpart:
                        record(topic, f"{topic}.{name}", source_kind, ids, text[start:end])
                        break
        classifications.append({"chunk_id": chunk["chunk_id"],
                                "proposed_topics": [t for t in VOCABULARY if t in topics],
                                "signals": signals})
    return {"schema_version": 1, "status": "completed", "classification_status": "provisional",
            "source_sha256": document["source_sha256"], "taxonomy_version": TAXONOMY_VERSION,
            "rules_version": RULES_VERSION, "taxonomy": list(VOCABULARY),
            "classifications": classifications}


@traced('B2')
def classify_chunks(artifact: ChunkArtifact, *, debug: bool = False,
                    run_id: str | None = None, trace_root: str | Path = 'tmp/runs') -> TopicSignalsArtifact:
    """Read B1 and atomically persist B2 guesses alongside it; no LLM call."""
    try:
        raw = artifact.chunks_json_path.read_bytes()
        document = json.loads(raw)
    except (OSError, ValueError) as error:
        raise InvalidTopicInputError("B1 artifact must contain readable JSON.") from error
    result = classify_chunk_document(document)
    if result["source_sha256"] != artifact.source_sha256:
        raise InvalidTopicInputError("B1 artifact source identity does not match its handle.")
    result["inputs"] = {"chunks_json_sha256": hashlib.sha256(raw).hexdigest()}
    destination = artifact.chunks_json_path.parent / "document.topic-signals.json"
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent, suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            json.dump(result, output, indent=2, ensure_ascii=False)
            output.write("\n")
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return TopicSignalsArtifact(artifact.source_sha256, destination, TAXONOMY_VERSION, RULES_VERSION)
