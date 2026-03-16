"""Orchestrates: ingest -> parse -> graph -> JSON output."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

import networkx as nx

from src.config import OUTPUT_JSON_DIR, OUTPUT_GRAPH_DIR
from src.ingestion.pdf_extractor import extract_pdf, ExtractionResult
from src.ingestion.ocr_fallback import ocr_flagged_pages
from src.ingestion.page_segmenter import segment_pages, TextBlock
from src.parsing.section_detector import detect_sections, SectionNode
from src.parsing.party_extractor import extract_parties
from src.parsing.facility_extractor import extract_facilities
from src.parsing.interest_extractor import extract_interest_terms
from src.parsing.table_parser import classify_table, parse_pricing_grid
from src.parsing.covenant_extractor import extract_covenants
from src.parsing.amendment_extractor import extract_amendments
from src.parsing.schedule_extractor import extract_schedules
from src.knowledge_graph.builder import build_graph, export_graph_json, export_graph_gexf
from src.models.schema import CreditAgreementDocument

logger = logging.getLogger(__name__)


def _generate_doc_id(file_path: Path) -> str:
    """Generate a short deterministic doc ID from the file name."""
    h = hashlib.md5(file_path.name.encode()).hexdigest()[:8]
    stem = file_path.stem[:40]
    return f"{stem}_{h}"


def _blocks_to_dicts(blocks: list[TextBlock]) -> list[dict]:
    """Convert TextBlock dataclasses to dicts for the parsing layer."""
    return [
        {
            "text": b.text,
            "block_idx": b.block_num,
            "page": b.page_num,
            "provenance_id": b.provenance_id,
        }
        for b in blocks
    ]


def _collect_all_tables(extraction: ExtractionResult) -> list[list[list[str]]]:
    """Flatten all tables from all pages into a single list."""
    tables = []
    for page in extraction.pages:
        for table in page.tables:
            # Normalize None cells to empty strings
            cleaned = [
                [str(cell) if cell is not None else "" for cell in row]
                for row in table
            ]
            tables.append(cleaned)
    return tables


def _extract_title(blocks: list[dict]) -> str:
    """Try to find the agreement title from the first few blocks."""
    for block in blocks[:5]:
        text = block.get("text", "").strip()
        upper_text = text.upper()
        if any(kw in upper_text for kw in ["CREDIT AGREEMENT", "FACILITY AGREEMENT",
                                            "LOAN AGREEMENT", "AMENDMENT"]):
            # Return first line as title
            return text.split("\n")[0].strip()[:200]
    return ""


def _extract_agreement_date(blocks: list[dict]) -> str:
    """Try to find the agreement date from the preamble."""
    import re
    date_pattern = re.compile(
        r"(?:dated\s+(?:as\s+of\s+)?)"
        r"((?:January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+\d{1,2},?\s+\d{4})",
        re.IGNORECASE,
    )
    for block in blocks[:10]:
        m = date_pattern.search(block.get("text", ""))
        if m:
            return m.group(1).strip()
    return ""


def process_document(
    pdf_path: str | Path,
    save_output: bool = True,
    progress_callback: Optional[callable] = None,
) -> tuple[CreditAgreementDocument, nx.DiGraph]:
    """Run the full parsing pipeline on a single PDF.

    Parameters
    ----------
    pdf_path:
        Path to the PDF file.
    save_output:
        If True, write JSON and graph files to the output directories.
    progress_callback:
        Optional callable(step: int, total: int, message: str) for
        reporting progress to the caller (e.g. Streamlit UI).

    Returns
    -------
    tuple[CreditAgreementDocument, nx.DiGraph]
        The parsed document model and its knowledge graph.
    """
    pdf_path = Path(pdf_path)
    doc_id = _generate_doc_id(pdf_path)
    logger.info("Processing %s (doc_id=%s)", pdf_path.name, doc_id)

    total_steps = 13

    def _progress(step: int, msg: str) -> None:
        logger.info(msg)
        if progress_callback:
            progress_callback(step, total_steps, msg)

    # ── Phase 1: Ingestion ────────────────────────────────────────────
    _progress(1, "Extracting text and tables from PDF...")
    extraction = extract_pdf(pdf_path)

    _progress(2, f"Extracted {extraction.metadata.total_pages} pages — running OCR on scanned pages...")
    extraction.pages = ocr_flagged_pages(pdf_path, extraction.pages)

    _progress(3, "Segmenting pages into text blocks...")
    blocks = segment_pages(extraction.pages, doc_id)
    block_dicts = _blocks_to_dicts(blocks)

    all_tables = _collect_all_tables(extraction)

    # ── Phase 2: Parsing ──────────────────────────────────────────────
    _progress(4, f"Detecting sections across {len(block_dicts)} blocks...")
    sections = detect_sections(block_dicts)

    _progress(5, "Extracting parties (borrower, lender, agent, guarantor)...")
    parties = extract_parties(block_dicts, doc_id)

    _progress(6, "Extracting facility details (type, amount, dates)...")
    facilities = extract_facilities(block_dicts, sections, doc_id)

    _progress(7, "Extracting interest rate terms (benchmark, spread, floor)...")
    interest_terms_list = extract_interest_terms(block_dicts, sections, doc_id)

    _progress(8, "Extracting covenants (financial, negative, affirmative)...")
    covenants = extract_covenants(block_dicts, sections, doc_id)

    _progress(9, "Extracting amendments and schedules...")
    amendments = extract_amendments(block_dicts, sections, doc_id)
    schedules = extract_schedules(block_dicts, sections, all_tables, doc_id)

    # Attach interest terms to facilities
    for i, facility in enumerate(facilities):
        if i < len(interest_terms_list):
            facility.interest_terms = interest_terms_list[i]
        elif interest_terms_list:
            facility.interest_terms = interest_terms_list[0]

    # Attach amortization schedules to facilities
    amort_schedules = schedules.get("amortization_schedules", [])
    for i, facility in enumerate(facilities):
        if i < len(amort_schedules):
            facility.amortization = amort_schedules[i]

    # Extract metadata
    _progress(10, "Extracting document title and date...")
    title = _extract_title(block_dicts)
    agreement_date = _extract_agreement_date(block_dicts)

    # ── Phase 3: Assemble Document ────────────────────────────────────
    _progress(11, "Assembling structured document...")
    doc = CreditAgreementDocument(
        doc_id=doc_id,
        file_name=pdf_path.name,
        title=title,
        agreement_date=agreement_date,
        effective_date=facilities[0].effective_date if facilities else "",
        parties=parties,
        facilities=facilities,
        covenants=covenants,
        amendments=amendments,
        total_pages=extraction.metadata.total_pages,
        extraction_metadata={
            "file_size_bytes": extraction.metadata.file_size_bytes,
            "total_blocks": len(block_dicts),
            "total_tables": len(all_tables),
            "sections_detected": len(sections),
            "ocr_pages": sum(1 for p in extraction.pages if p.needs_ocr),
        },
    )

    # ── Phase 4: Knowledge Graph ──────────────────────────────────────
    _progress(12, "Building knowledge graph...")
    graph = build_graph(doc)

    # ── Save output ───────────────────────────────────────────────────
    _progress(13, "Saving JSON and graph output...")
    if save_output:
        json_path = OUTPUT_JSON_DIR / f"{doc_id}.json"
        with open(json_path, "w") as f:
            f.write(doc.model_dump_json(indent=2))
        logger.info("Saved JSON to %s", json_path)

        graph_json_path = OUTPUT_GRAPH_DIR / f"{doc_id}_graph.json"
        export_graph_json(graph, graph_json_path)
        logger.info("Saved graph to %s", graph_json_path)

    return doc, graph


def process_batch(
    pdf_dir: str | Path,
    limit: Optional[int] = None,
) -> list[tuple[str, bool, str]]:
    """Process all PDFs in a directory.

    Returns
    -------
    list[tuple[str, bool, str]]
        (filename, success, error_message) for each file.
    """
    pdf_dir = Path(pdf_dir)
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if limit:
        pdfs = pdfs[:limit]

    results = []
    for pdf_path in pdfs:
        try:
            process_document(pdf_path)
            results.append((pdf_path.name, True, ""))
            logger.info("OK: %s", pdf_path.name)
        except Exception as e:
            results.append((pdf_path.name, False, str(e)))
            logger.error("FAIL: %s — %s", pdf_path.name, e)

    # Summary
    success = sum(1 for _, ok, _ in results if ok)
    logger.info("Batch complete: %d/%d succeeded", success, len(results))
    return results
