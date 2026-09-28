"""Behavioral tests for the provisional party-extraction JSON contract."""

import json

from credit_agreement_extractor.models import (
    ExtractionResult,
    ExtractionStatus,
    ParentCompany,
    Party,
)


def test_result_serializes_unknown_parent_as_json_null() -> None:
    """Unknown corporate ownership must remain unknown, never guessed."""
    result = ExtractionResult(
        document_name="agreement.pdf",
        status=ExtractionStatus.COMPLETED,
        borrowers=[
            Party(
                name="Example Borrower, Inc.",
                role="borrower",
                is_primary=True,
                parent=None,
            )
        ],
    )

    payload = result.model_dump(mode="json")

    assert payload["borrowers"][0]["parent"] is None
    assert json.loads(json.dumps(payload))["borrowers"][0]["parent"] is None


def test_parent_relationship_is_preserved_verbatim() -> None:
    """The model stores an evidenced relationship without normalizing its meaning."""
    party = Party(
        name="Example Borrower, Inc.",
        role="borrower",
        is_primary=True,
        parent=ParentCompany(
            name="Example Holdings, Inc.",
            relationship="Example Holdings directly owns Example Borrower.",
        ),
    )

    assert party.parent is not None
    assert party.parent.relationship == (
        "Example Holdings directly owns Example Borrower."
    )


def test_empty_collections_are_created_per_result() -> None:
    """Default lists must not be shared between extraction results."""
    first = ExtractionResult(
        document_name="first.pdf",
        status=ExtractionStatus.NOT_IMPLEMENTED,
    )
    second = ExtractionResult(
        document_name="second.pdf",
        status=ExtractionStatus.NOT_IMPLEMENTED,
    )

    first.errors.append("first-only")

    assert second.errors == []
