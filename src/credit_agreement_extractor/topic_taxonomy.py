"""Versioned, editable English vocabulary agreed for B2's initial guesses.

These phrases indicate possible relevance, not legal conclusions. B3 will
review the proposals against source evidence. Keep historical benchmarks:
older agreements remain useful even when their reference rates have ceased.
"""

TAXONOMY_VERSION = "credit-topics-v1"
RULES_VERSION = "b2-phrases-v1"
TOPIC_DEFINITIONS_VERSION = "credit-topic-definitions-v1"

# Shared classification meanings, separate from B2's deliberately broad phrase
# rules. B3 receives these definitions with each batch; reviewers can use the
# same boundaries. Topic IDs and existing provisional B2 matches are unchanged.
TOPIC_DEFINITIONS = {
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
VOCABULARY = {
    "parties_and_roles": (
        "borrower", "borrowers", "co-borrower", "co-borrowers", "lender", "lenders",
        "original borrower", "additional borrower", "original lender",
        "administrative agent", "facility agent", "collateral agent", "security agent",
        "guarantor", "guarantors", "parent", "holdings", "finance parties", "obligors",
        "as borrower", "as lender", "parties hereto", "original parties",
    ),
    "facility_and_commitment_terms": (
        "term loan", "revolving facility", "revolving credit facility", "credit facility",
        "delayed draw term loan", "bridge facility", "bridge loan", "line of credit",
        "credit line", "commitment", "commitments", "aggregate commitments",
        "total commitments", "facility amount", "revolving commitment",
        "term loan commitment", "borrowing base", "availability period",
        "commitment period", "drawdown", "utilisation", "utilization",
        "borrowing request", "funding date", "facility drawdown", "first draw",
        "incremental facility", "accordion", "commitment increase",
        "commitment reduction", "cancellation of commitments",
    ),
    "interest_and_fees": (
        "interest", "interest rate", "rate of interest", "applicable rate",
        "applicable margin", "margin", "spread", "pricing ratchet", "margin ratchet",
        "ratchet grid", "pricing grid", "applicable margin table", "pricing level",
        "pricing tier", "SOFR", "Term SOFR", "SONIA", "EURIBOR", "LIBOR",
        "base rate", "prime rate", "reference rate", "HIBOR", "HONIA", "STIBOR",
        "NIBOR", "BBSW", "BBSY", "CORRA", "CDOR", "TIBOR", "Euroyen TIBOR",
        "SOR", "SIBOR", "SORA", "KLIBOR", "BKBM", "THBFIX", "SARON",
        "TONA", "TONAR", "ESTR", "€STR", "AONIA", "AUD LIBOR",
        "bank bill swap rate", "Canadian dollar offered rate",
        "Hong Kong interbank offered rate", "Stockholm interbank offered rate",
        "secured overnight financing rate", "sterling overnight index average",
        "interest period", "interest payment date", "accrued interest",
        "day count", "day count convention", "day count basis", "default interest",
        "interest rate floor", "actual/360", "actual/365", "actual/actual", "30/360",
        "360-day year", "365-day year", "actual number of days elapsed",
        "fee", "fees", "commitment fee", "arrangement fee", "upfront fee",
        "facility fee", "agency fee", "unused line fee", "ticking fee", "ticking fees",
    ),
    "interest_and_fees.pik_toggle": (
        "payment in kind", "payment-in-kind", "PIK", "PIK interest", "PIK election",
        "PIK toggle", "capitalised interest", "capitalized interest", "cash/PIK",
    ),
    "maturity_termination_extension": (
        "maturity date", "final maturity date", "scheduled maturity date",
        "termination date", "final repayment date", "repayment date",
        "facility termination", "termination of commitments", "cancellation of commitments",
        "expiry date", "expiration date", "extension option", "extension request",
        "maturity extension", "extension of maturity", "extended maturity date",
        "extension period", "extension fee", "extension notice", "non-extending lender",
        "extending lender", "extension election", "springing maturity",
        "springing maturity date", "latest maturity date",
    ),
    "repayment_and_prepayment": (
        "repayment", "principal payment", "instalment", "installment", "amortisation",
        "amortization", "repayment schedule", "balloon payment", "bullet repayment",
        "voluntary prepayment", "optional prepayment", "prepayment notice",
        "prepayment election", "mandatory prepayment", "excess cash flow", "cash sweep",
        "asset sale proceeds", "net cash proceeds", "debt issuance proceeds",
        "application of payments", "application of proceeds", "payment waterfall",
        "pro rata payment", "order of application",
    ),
    "repayment_and_prepayment.call_protection": (
        "prepayment premium", "call premium", "make-whole", "make whole", "soft call",
        "hard call", "no-call period", "repricing transaction", "repricing premium",
        "early repayment fee",
    ),
    "covenants": (
        "covenants", "covenant", "undertakings", "affirmative covenants",
        "negative covenants", "financial covenants", "information undertakings",
        "leverage ratio", "interest coverage ratio", "fixed charge coverage ratio",
        "debt service coverage ratio", "minimum liquidity", "minimum EBITDA", "net worth",
        "permitted indebtedness", "permitted liens", "restricted payments",
        "distributions", "investments", "asset disposals", "change of business",
        "financial statements", "compliance certificate", "reporting requirements",
        "notice of default", "test date", "testing period", "covenant compliance",
        "covenant breach", "equity cure", "cure right", "covenant holiday", "springing covenant",
    ),
    "guarantees_and_security": (
        "guarantee", "guaranty", "guaranteed obligations", "guarantee and indemnity",
        "subsidiary guarantee", "parent guarantee", "collateral", "security interest",
        "security documents", "security agreement", "secured obligations",
        "collateral documents", "pledge", "mortgage", "charge", "debenture",
        "assignment by way of security", "grant of security", "perfection",
        "perfected security interest", "collateral coverage", "release of collateral",
        "release of guarantees", "lien priority", "first lien", "second lien",
        "intercreditor agreement", "subordination",
    ),
    "default_and_remedies": (
        "event of default", "events of default", "default", "potential event of default",
        "failure to pay", "non-payment", "breach of covenant", "misrepresentation",
        "cross-default", "cross-acceleration", "insolvency", "bankruptcy",
        "change of control", "grace period", "cure period", "remedy period",
        "default notice", "acceleration", "immediately due and payable", "enforcement",
        "exercise of remedies", "cancellation of commitments", "required lenders",
        "majority lenders", "enforcement instructions",
    ),
}

PARENT_TOPICS = {
    "interest_and_fees.pik_toggle": "interest_and_fees",
    "repayment_and_prepayment.call_protection": "repayment_and_prepayment",
}

# Context rules use a bounded same-item/content window. Frequency wording alone
# cannot distinguish interest payments from covenant reporting obligations.
CONTEXT_RULES = (
    ("interest_and_fees", "payment_timing", r"\binterest\b", r"\b(?:in arrears|in arears|in advance|monthly|quarterly|semi[ -]annually)\b"),
    ("interest_and_fees", "ratio_pricing", r"\b(?:margin|spread|pricing)\b", r"\b(?:leverage|coverage|rating|ratings)\b"),
    ("maturity_termination_extension", "conditional_date", r"\b(?:maturity|termination|facility)\b", r"\bearlier of\b"),
)
