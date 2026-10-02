"""Shared versioned topic IDs and classification meanings."""

TAXONOMY_VERSION = "credit-topics-v2"
TOPIC_DEFINITIONS_VERSION = "credit-topic-definitions-v2"

TOPIC_DEFINITIONS = {
    "contract_definitions": (
        "Passages defining contractual terms, including dedicated definitions "
        "sections and definitions embedded in operative clauses. Merely using "
        "a defined term does not qualify. Also assign substantive topics where "
        "the definition supplies useful evidence about that topic."
    ),
    "parties_and_roles": (
        "Identities, transaction roles, parent companies, and relationships among "
        "borrowers, lenders, guarantors, and agents. Merely mentioning Borrower "
        "or Lender is not sufficient."
    ),
    "facility_and_commitment_terms": (
        "Facility types, loan amounts, commitments, borrowing bases, availability, "
        "drawdowns, and conditions for borrowing."
    ),
    "interest_and_fees": (
        "Interest rates, benchmarks, margins, pricing grids, accrual conventions, "
        "interest-payment timing, and facility-related fees. Prepayment premiums "
        "belong under repayment/prepayment and call protection, not here merely "
        "because they are called fees."
    ),
    "interest_and_fees.pik_toggle": (
        "Payment-in-kind options and elections, including capitalization of "
        "interest instead of cash payment. Subtopic of interest_and_fees."
    ),
    "maturity_termination_extension": (
        "Maturity dates, expiry, termination rights, and provisions extending "
        "maturity or availability."
    ),
    "repayment_and_prepayment": (
        "Principal repayment, amortization, voluntary and mandatory prepayments, "
        "and application of repayments; includes call-protection provisions."
    ),
    "repayment_and_prepayment.call_protection": (
        "Early-repayment restrictions, prepayment premiums, penalties, and "
        "make-whole amounts. Subtopic of repayment_and_prepayment."
    ),
    "covenants": (
        "Ongoing obligations and restrictions, including financial tests, reporting "
        "duties, affirmative covenants, and negative covenants."
    ),
    "guarantees_and_security": (
        "Guarantees, collateral, security interests, liens, priority, and release "
        "of guarantees or security."
    ),
    "default_and_remedies": (
        "Events of default, cure periods, acceleration, enforcement, and lender "
        "remedies. A missed-interest-payment default belongs here; also label "
        "interest_and_fees only if it establishes substantive interest terms."
    ),
}
# Dictionary order defines deterministic output order, including subtopics.
VOCABULARY = tuple(TOPIC_DEFINITIONS)

PARENT_TOPICS = {
    "interest_and_fees.pik_toggle": "interest_and_fees",
    "repayment_and_prepayment.call_protection": "repayment_and_prepayment",
}
