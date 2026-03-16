"""Extract parties with precision-first filtering.

Combines role-aware regex and spaCy ORG detection, then applies
strict validation so narrative/legal prose is not mislabeled as parties.
"""

from __future__ import annotations

import re
from typing import Optional

import spacy

from src.field_patterns import PARTY_ROLE_SYNONYMS
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
# Role-detection regex patterns — built from centralized PARTY_ROLE_SYNONYMS
# ---------------------------------------------------------------------------

_ROLE_ONLY_NAMES = {
    "borrower",
    "co borrower",
    "co-borrower",
    "lender",
    "lenders",
    "administrative agent",
    "agent",
    "facility agent",
    "guarantor",
    "guarantors",
    "arranger",
    "arrangers",
    "credit agreement",
    "definitions",
}

_GENERIC_NON_PARTY_TERMS = {
    "effective date",
    "conversion",
    "warranties",
    "definitions",
    "taxes",
    "credit agreement",
    "executed counterparts",
    "commitment",
    "termination date",
    "class b revolving commitment",
    "fronting bank",
    "federal reserve bank",
    "letters of credit",
    "bank, ltd",
}

_NON_NAME_WORDS_RE = re.compile(
    r"\b("
    r"has|have|having|requested|requests|requesting|hereby|shall|will|"
    r"among|other|things|that|reduce|increase|amend|ratify|ratifies|ratified|"
    r"affirms|affirm|party|thereto|hereunder|hereto|pursuant|whereas"
    r")\b",
    re.IGNORECASE,
)

_ROLE_OR_GENERIC_WORDS_RE = re.compile(
    r"\b("
    r"borrower|lender|lenders|guarantor|guarantors|arranger|arrangers|"
    r"administrative\s+agent|facility\s+agent|agent|agreement|commitment|"
    r"regulation|certification|termination|date|ownership|swingline|conversion|"
    r"definitions|warranties|taxes"
    r")\b",
    re.IGNORECASE,
)

_ENTITY_MARKER_RE = re.compile(
    r"\b("
    r"bank|n\.a\.?|inc\.?|llc|ltd\.?|limited|corp\.?|corporation|company|co\.|"
    r"plc|lp|l\.p\.|partners?|holdings?|trust|association|securities|capital|"
    r"group|finance|s\.a\.?|ag|gmbh"
    r")\b",
    re.IGNORECASE,
)


def _is_valid_party_name(name: str) -> bool:
    """Return True only for names that look like real legal entities."""
    normalized = " ".join(name.strip().split())
    if len(normalized) < 3:
        return False
    if len(normalized) > 160:
        return False

    lowered = normalized.lower()
    lowered_no_article = re.sub(r"^(?:the|each|a|an)\s+", "", lowered).strip()
    if lowered in _ROLE_ONLY_NAMES:
        return False
    if lowered in _GENERIC_NON_PARTY_TERMS:
        return False
    if lowered_no_article in _GENERIC_NON_PARTY_TERMS:
        return False
    if _NON_NAME_WORDS_RE.search(lowered):
        return False
    if _ROLE_OR_GENERIC_WORDS_RE.search(lowered):
        return False

    tokens = [t.strip(".,;:()[]\"'") for t in normalized.split() if t.strip(".,;:()[]\"'")]
    if not tokens:
        return False

    if len(tokens) == 1:
        tok = tokens[0]
        low = tok.lower()
        if len(tok) <= 4:
            return False
        if low in {"ltd", "inc", "llc", "corp", "co", "bank", "n.a", "na", "plc", "lp"}:
            return False

    # Precision-first: require names to look like legal entities.
    if not _ENTITY_MARKER_RE.search(normalized):
        return False

    return True

_ROLE_PATTERNS: list[tuple[str, re.Pattern[str]]] = []
for _role, _synonyms in PARTY_ROLE_SYNONYMS.items():
    _alt = "|".join(f"(?:{s})" for s in _synonyms)
    _ROLE_PATTERNS.append((
        _role,
        re.compile(
            # Require punctuation after role keyword (",", ":" or ")")
            # so narrative text like "Borrower has requested..." is ignored.
            rf'(?i:(?:{_alt}))["\u201c\u201d]?\s*[,):]\s*'
            rf'([A-Z][A-Za-z0-9&.,\-\']*(?:\s+(?:[A-Z0-9][A-Za-z0-9&.,\-\']*|and|of|the|&)){{0,18}})',
        ),
    ))


def _clean_name(raw: str) -> str:
    """Trim trailing noise from a captured entity name."""
    first_line = raw.strip().splitlines()[0]
    name = " ".join(first_line.split()).rstrip(",;:.")
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
                if not _is_valid_party_name(name):
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
                if not _is_valid_party_name(name):
                    continue
                context = text[max(0, ent.start_char - 80): ent.end_char + 80].lower()
                role = _infer_role_from_context(context)
                if role == "unknown":
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
                                text_snippet=ent.text[:120],
                            ),
                        )
                    )

    return parties


def _infer_role_from_context(context: str) -> str:
    """Guess a party role from the surrounding text.

    Uses all canonical roles from ``PARTY_ROLE_SYNONYMS`` to match
    keywords in the context window.
    """
    _role_kw_map: list[tuple[str, str]] = [
        (role, role.replace("_", " "))
        for role in PARTY_ROLE_SYNONYMS
    ]
    for role, kw in _role_kw_map:
        if kw in context:
            return role
    return "unknown"
