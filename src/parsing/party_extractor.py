"""Extracts parties (borrower, lender, administrative agent, guarantor)
from credit agreement text blocks using spaCy NER and regex."""

from __future__ import annotations

import re
from typing import Optional

import spacy

from src.models.schema import Party, SourceRef

# ---------------------------------------------------------------------------
# Lazy-load spaCy model
# ---------------------------------------------------------------------------

_NLP: Optional[spacy.language.Language] = None


def _get_nlp() -> spacy.language.Language:
    global _NLP
    if _NLP is None:
        _NLP = spacy.load("en_core_web_sm")
    return _NLP


# ---------------------------------------------------------------------------
# Role-detection regex patterns
# ---------------------------------------------------------------------------

_ROLE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "borrower",
        re.compile(
            r'(?:the\s+)?["\u201c\u201d]?Borrower["\u201c\u201d]?\s*[,):\s]+\s*([A-Z][A-Za-z0-9 &.,\-\']+)',
            re.IGNORECASE,
        ),
    ),
    (
        "lender",
        re.compile(
            r'(?:the\s+)?["\u201c\u201d]?Lenders?["\u201c\u201d]?\s*[,):\s]+\s*([A-Z][A-Za-z0-9 &.,\-\']+)',
            re.IGNORECASE,
        ),
    ),
    (
        "administrative_agent",
        re.compile(
            r'(?:the\s+)?["\u201c\u201d]?Administrative\s+Agent["\u201c\u201d]?\s*[,):\s]+\s*([A-Z][A-Za-z0-9 &.,\-\']+)',
            re.IGNORECASE,
        ),
    ),
    (
        "guarantor",
        re.compile(
            r'(?:the\s+)?["\u201c\u201d]?Guarantors?["\u201c\u201d]?\s*[,):\s]+\s*([A-Z][A-Za-z0-9 &.,\-\']+)',
            re.IGNORECASE,
        ),
    ),
    (
        "arranger",
        re.compile(
            r'(?:the\s+)?["\u201c\u201d]?(?:Lead\s+)?Arrangers?["\u201c\u201d]?\s*[,):\s]+\s*([A-Z][A-Za-z0-9 &.,\-\']+)',
            re.IGNORECASE,
        ),
    ),
]


def _clean_name(raw: str) -> str:
    """Trim trailing noise from a captured entity name."""
    name = raw.strip().rstrip(",;:.")
    for stop in ("(the ", "(herein", "(collectively", ", a ", ", an "):
        idx = name.lower().find(stop)
        if idx > 0:
            name = name[:idx].strip()
    return name


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_parties(blocks: list[dict], doc_id: str = "") -> list[Party]:
    """Extract party information from credit agreement *blocks*.

    Focuses on the preamble (first ~5 blocks) and signature pages
    (last ~20 blocks) where party names are most reliably stated.
    """
    if not blocks:
        return []

    preamble = blocks[: min(5, len(blocks))]
    signatures = blocks[-min(20, len(blocks)):]
    focus_blocks = preamble + signatures

    seen: set[tuple[str, str]] = set()
    parties: list[Party] = []

    for block in focus_blocks:
        text: str = block.get("text", "")
        block_idx: Optional[int] = block.get("block_idx")
        page: Optional[int] = block.get("page")

        # --- Regex-based extraction ---
        for role, pattern in _ROLE_PATTERNS:
            for m in pattern.finditer(text):
                name = _clean_name(m.group(1))
                if not name or len(name) < 3:
                    continue
                key = (name.lower(), role)
                if key not in seen:
                    seen.add(key)
                    parties.append(
                        Party(
                            name=name,
                            role=role,
                            source_ref=SourceRef(
                                doc_id=doc_id,
                                page=page,
                                block=block_idx,
                                text_snippet=m.group(0)[:120],
                            ),
                        )
                    )

        # --- spaCy NER fallback for ORG entities ---
        nlp = _get_nlp()
        doc = nlp(text[:5000])
        for ent in doc.ents:
            if ent.label_ == "ORG":
                name = _clean_name(ent.text)
                if not name or len(name) < 3:
                    continue
                context = text[max(0, ent.start_char - 80): ent.end_char + 80].lower()
                role = _infer_role_from_context(context)
                key = (name.lower(), role)
                if key not in seen:
                    seen.add(key)
                    parties.append(
                        Party(
                            name=name,
                            role=role,
                            source_ref=SourceRef(
                                doc_id=doc_id,
                                page=page,
                                block=block_idx,
                                text_snippet=ent.text[:120],
                            ),
                        )
                    )

    return parties


def _infer_role_from_context(context: str) -> str:
    """Guess a party role from the surrounding text."""
    role_keywords = [
        ("borrower", "borrower"),
        ("lender", "lender"),
        ("administrative_agent", "administrative agent"),
        ("guarantor", "guarantor"),
        ("arranger", "arranger"),
    ]
    for role, kw in role_keywords:
        if kw in context:
            return role
    return "unknown"
