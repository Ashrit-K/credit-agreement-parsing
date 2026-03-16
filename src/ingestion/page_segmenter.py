"""Split extracted page text into provenance-tagged blocks and lines."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.ingestion.pdf_extractor import PageData


@dataclass
class TextBlock:
    """A contiguous paragraph-level block extracted from one page."""

    text: str
    provenance_id: str
    page_num: int
    block_num: int
    lines: list[tuple[str, str]] = field(default_factory=list)
    # lines is a list of (line_text, provenance_id) tuples
    section_heading: str | None = None  # optional section context for later use


def _make_provenance(doc_id: str, page: int, block: int, line: int | None = None) -> str:
    """Build a provenance ID string following the project convention.

    Format: ``{doc_id}/p{page}/b{block}`` or ``{doc_id}/p{page}/b{block}/l{line}``
    """
    pid = f"{doc_id}/p{page}/b{block}"
    if line is not None:
        pid += f"/l{line}"
    return pid


_HEADING_PATTERN = re.compile(
    r"^(?:ARTICLE|SECTION|EXHIBIT|SCHEDULE|ANNEX)\s+[IVXLCDM\d]+",
    re.IGNORECASE,
)


def _detect_section_heading(text: str) -> str | None:
    """Return the first line if it looks like a section/article heading."""
    first_line = text.split("\n", 1)[0].strip()
    if _HEADING_PATTERN.match(first_line):
        return first_line
    return None


def segment_pages(
    pages: list[PageData],
    doc_id: str,
) -> list[TextBlock]:
    """Segment page texts into blocks with provenance IDs.

    Paragraphs are identified by splitting on double newlines (``\\n\\n``).
    Each block is further split into individual lines for fine-grained
    provenance tracking.

    Parameters
    ----------
    pages:
        Output of ``pdf_extractor.extract_pdf``.
    doc_id:
        Unique document identifier used as the root of every provenance ID.

    Returns
    -------
    list[TextBlock]
        Ordered list of text blocks across all pages.
    """
    blocks: list[TextBlock] = []
    current_section: str | None = None

    for page_data in pages:
        if not page_data.text.strip():
            continue

        # Split on two or more consecutive newlines to get paragraph blocks
        raw_blocks = re.split(r"\n{2,}", page_data.text)

        for block_idx, raw_block in enumerate(raw_blocks, start=1):
            raw_block = raw_block.strip()
            if not raw_block:
                continue

            # Check if this block starts a new section
            heading = _detect_section_heading(raw_block)
            if heading is not None:
                current_section = heading

            block_prov = _make_provenance(doc_id, page_data.page_num, block_idx)

            # Split block into individual lines
            raw_lines = raw_block.split("\n")
            lines: list[tuple[str, str]] = []
            for line_idx, line_text in enumerate(raw_lines, start=1):
                line_text = line_text.strip()
                if not line_text:
                    continue
                line_prov = _make_provenance(
                    doc_id, page_data.page_num, block_idx, line_idx
                )
                lines.append((line_text, line_prov))

            text_block = TextBlock(
                text=raw_block,
                provenance_id=block_prov,
                page_num=page_data.page_num,
                block_num=block_idx,
                lines=lines,
                section_heading=current_section,
            )
            blocks.append(text_block)

    return blocks
