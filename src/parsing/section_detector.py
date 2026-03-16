"""Detects ARTICLE and SECTION headers in credit agreement text blocks
and builds a hierarchical section tree."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Regex patterns for credit-agreement headings
# ---------------------------------------------------------------------------

_ARTICLE_ROMAN = re.compile(
    r"^\s*ARTICLE\s+([IVXLCDM]+)\b[.\s]*(.*)$", re.IGNORECASE
)
_ARTICLE_ARABIC = re.compile(
    r"^\s*ARTICLE\s+(\d+)\b[.\s]*(.*)$", re.IGNORECASE
)
_SECTION_DOTTED = re.compile(
    r"^\s*(?:SECTION|Section)\s+(\d+\.\d+)\b[.\s]*(.*)$"
)

# Fallback pattern for numbered headings like "1.01  Definitions"
_SECTION_LOOSE = re.compile(
    r"^\s*(\d{1,3}\.\d{1,3})\s{2,}([A-Z].*)"
)


@dataclass
class SectionNode:
    """A node in the section hierarchy of a credit agreement."""

    title: str
    level: str  # "article" or "section"
    number: str  # e.g. "II", "2", "2.01"
    start_block_idx: int
    end_block_idx: int = -1
    children: list[SectionNode] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    @property
    def full_heading(self) -> str:
        prefix = "ARTICLE" if self.level == "article" else "Section"
        return f"{prefix} {self.number} — {self.title}".strip(" —")

    def walk(self) -> list[SectionNode]:
        """Yield self plus all descendants in pre-order."""
        result: list[SectionNode] = [self]
        for child in self.children:
            result.extend(child.walk())
        return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_sections(blocks: list[dict]) -> list[SectionNode]:
    """Scan *blocks* (each with a ``text`` key) and return a list of
    top-level :class:`SectionNode` objects with children populated.

    Parameters
    ----------
    blocks:
        Ordered list of text blocks, each a dict with at least a ``text``
        key (and optionally ``block_idx``, ``page``).

    Returns
    -------
    list[SectionNode]
        Top-level ARTICLE nodes, each containing child SECTION nodes.
    """
    raw_nodes: list[SectionNode] = []

    for idx, block in enumerate(blocks):
        text: str = block.get("text", "")
        first_line = text.split("\n", 1)[0].strip()

        # Try ARTICLE patterns first
        m = _ARTICLE_ROMAN.match(first_line) or _ARTICLE_ARABIC.match(first_line)
        if m:
            number = m.group(1).strip()
            title = m.group(2).strip().strip(".")
            # If title is empty, check the next line
            if not title:
                lines = text.split("\n")
                if len(lines) > 1:
                    title = lines[1].strip().strip(".")
            raw_nodes.append(
                SectionNode(
                    title=title,
                    level="article",
                    number=number,
                    start_block_idx=idx,
                )
            )
            continue

        # Try SECTION patterns
        m = _SECTION_DOTTED.match(first_line) or _SECTION_LOOSE.match(first_line)
        if m:
            number = m.group(1).strip()
            title = m.group(2).strip().strip(".")
            raw_nodes.append(
                SectionNode(
                    title=title,
                    level="section",
                    number=number,
                    start_block_idx=idx,
                )
            )

    # ------------------------------------------------------------------
    # Assign end_block_idx and build parent-child hierarchy
    # ------------------------------------------------------------------
    total_blocks = len(blocks)
    for i, node in enumerate(raw_nodes):
        if i + 1 < len(raw_nodes):
            node.end_block_idx = raw_nodes[i + 1].start_block_idx - 1
        else:
            node.end_block_idx = total_blocks - 1

    # Build hierarchy: sections belong to preceding article
    top_level: list[SectionNode] = []
    current_article: Optional[SectionNode] = None

    for node in raw_nodes:
        if node.level == "article":
            current_article = node
            top_level.append(node)
        elif node.level == "section":
            if current_article is not None:
                current_article.children.append(node)
            else:
                # Orphan section — promote to top-level
                top_level.append(node)

    return top_level


def find_section_by_keyword(
    sections: list[SectionNode], keyword: str
) -> list[SectionNode]:
    """Return every :class:`SectionNode` (at any depth) whose *title*
    contains *keyword* (case-insensitive).

    Parameters
    ----------
    sections:
        Top-level nodes returned by :func:`detect_sections`.
    keyword:
        Search term, e.g. ``"INTEREST"``, ``"COVENANTS"``.

    Returns
    -------
    list[SectionNode]
    """
    keyword_lower = keyword.lower()
    matches: list[SectionNode] = []
    for top_node in sections:
        for node in top_node.walk():
            if keyword_lower in node.title.lower():
                matches.append(node)
    return matches
