"""Tests for party extraction precision (false-positive controls)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.parsing.party_extractor as party_extractor


class _DummyNLPNoEnts:
    def __call__(self, text: str):
        return SimpleNamespace(ents=[])


class _DummyNLPWithOrg:
    def __call__(self, text: str):
        ent = SimpleNamespace(
            label_="ORG",
            text="DEFINITIONS",
            start_char=0,
            end_char=min(len(text), len("DEFINITIONS")),
        )
        return SimpleNamespace(ents=[ent])


def test_role_regex_does_not_capture_sentence_fragments(monkeypatch):
    monkeypatch.setattr(party_extractor, "_get_nlp", lambda: _DummyNLPNoEnts())
    blocks = [
        {
            "text": "the Borrower has requested, among other things, that the Lender reduce commitment.",
            "block_idx": 1,
            "page": 1,
        }
    ]

    parties = party_extractor.extract_parties(blocks, doc_id="doc")

    assert parties == []


def test_ner_unknown_role_entities_are_not_emitted(monkeypatch):
    monkeypatch.setattr(party_extractor, "_get_nlp", lambda: _DummyNLPWithOrg())
    blocks = [{"text": "DEFINITIONS", "block_idx": 1, "page": 1}]

    parties = party_extractor.extract_parties(blocks, doc_id="doc")

    assert parties == []
