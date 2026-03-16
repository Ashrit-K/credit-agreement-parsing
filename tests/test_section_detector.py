"""Tests for section detection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.parsing.section_detector import detect_sections, find_section_by_keyword


def test_detect_article_roman():
    blocks = [
        {"text": "Preamble text here"},
        {"text": "ARTICLE I\nDEFINITIONS"},
        {"text": "Some definitions text"},
        {"text": "ARTICLE II\nTHE CREDITS"},
        {"text": "Credit terms here"},
        {"text": "Section 2.01  Commitments\nThe lenders agree..."},
        {"text": "Section 2.02  Loans\nEach borrowing..."},
    ]
    sections = detect_sections(blocks)
    assert len(sections) == 2
    assert sections[0].level == "article"
    assert sections[0].number == "I"
    assert sections[1].number == "II"


def test_detect_sections_under_article():
    blocks = [
        {"text": "ARTICLE II\nTHE CREDITS"},
        {"text": "Section 2.01  Commitments\nThe lenders agree..."},
        {"text": "Section 2.02  Loans\nEach borrowing..."},
    ]
    sections = detect_sections(blocks)
    assert len(sections) == 1  # One article
    assert len(sections[0].children) == 2  # Two child sections


def test_find_section_by_keyword():
    blocks = [
        {"text": "ARTICLE I\nDEFINITIONS"},
        {"text": "ARTICLE VI\nFINANCIAL COVENANTS"},
        {"text": "Section 6.01  Maximum Leverage Ratio"},
    ]
    sections = detect_sections(blocks)
    matches = find_section_by_keyword(sections, "COVENANTS")
    assert len(matches) >= 1
    assert "COVENANTS" in matches[0].title.upper()
