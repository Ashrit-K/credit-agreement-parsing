"""Centralized synonym and regex pattern definitions for all extracted fields.

Every extractor imports its patterns from this file. To expand coverage,
add new synonyms or regex alternatives here — no extractor code changes needed.

Structure:
    Each field group is a dict mapping a canonical label to a list of regex
    pattern strings.  The helper ``compile_patterns()`` turns them into
    compiled ``re.Pattern`` objects at import time.

    For simple keyword lists (e.g. section-targeting keywords), plain
    string lists are used instead of regex.
"""

from __future__ import annotations

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Helper: compile a dict of label -> [pattern_str, ...] into
#         list of (label, compiled_re) tuples
# ---------------------------------------------------------------------------

def compile_patterns(
    mapping: dict[str, list[str]],
    flags: int = re.IGNORECASE,
) -> list[tuple[str, re.Pattern[str]]]:
    """Compile a {label: [pattern_strings]} dict into [(label, regex)] pairs.

    Multiple pattern strings for the same label are joined with ``|`` so
    that a single compiled regex covers all synonyms.
    """
    result: list[tuple[str, re.Pattern[str]]] = []
    for label, patterns in mapping.items():
        combined = "|".join(f"(?:{p})" for p in patterns)
        result.append((label, re.compile(combined, flags)))
    return result


# ═══════════════════════════════════════════════════════════════════════════
# SECTION TARGETING — keywords used to locate relevant ARTICLE/SECTION ranges
# ═══════════════════════════════════════════════════════════════════════════

SECTION_KEYWORDS: dict[str, list[str]] = {
    "facility": [
        "COMMITMENT", "FACILITY", "LOAN", "THE CREDITS",
        "CREDIT FACILITY", "TERM LOAN", "REVOLVING",
        "AMOUNTS AND TERMS", "THE LOANS", "CREDIT EXTENSIONS",
    ],
    "interest": [
        "INTEREST", "RATE", "PRICING", "APPLICABLE MARGIN",
        "APPLICABLE RATE", "APPLICABLE PERCENTAGE", "BENCHMARK",
        "YIELD", "COUPON",
    ],
    "covenant_financial": [
        "FINANCIAL COVENANT", "FINANCIAL TEST",
        "LEVERAGE", "COVERAGE", "FINANCIAL CONDITION",
        "FINANCIAL REQUIREMENT", "FINANCIAL RATIO",
    ],
    "covenant_negative": [
        "NEGATIVE COVENANT", "RESTRICTIVE COVENANT",
        "LIMITATIONS", "PROHIBITED TRANSACTIONS",
    ],
    "covenant_affirmative": [
        "AFFIRMATIVE COVENANT", "POSITIVE COVENANT",
        "REPORTING", "INFORMATION COVENANT",
    ],
    "amendment": [
        "AMENDMENT", "MODIFICATION", "WAIVER",
        "CONSENT", "SUPPLEMENT",
    ],
    "schedule": [
        "SCHEDULE", "EXHIBIT", "AMORTIZATION", "REPAYMENT",
        "ANNEX", "APPENDIX",
    ],
    "prepayment": [
        "PREPAYMENT", "CALL", "REDEMPTION",
        "VOLUNTARY PREPAYMENT", "MANDATORY PREPAYMENT",
        "OPTIONAL PREPAYMENT",
    ],
    "fees": [
        "FEE", "TICKING", "COMMITMENT FEE",
        "AGENCY FEE", "UPFRONT FEE", "FACILITY FEE",
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
# FACILITY TYPE patterns
# ═══════════════════════════════════════════════════════════════════════════

FACILITY_TYPE_SYNONYMS: dict[str, list[str]] = {
    "revolving": [
        r"revolving\s+(?:credit\s+)?(?:facility|commitment|loan)",
        r"revolving\s+line\s+of\s+credit",
        r"revolving\s+credit\s+agreement",
        r"revolver",
        r"RCF\b",
    ],
    "term_loan_b": [
        r"term\s+(?:loan\s+)?b\b",
        r"term\s+b\s+(?:loan|facility)",
        r"TLB\b",
        r"tranche\s+b\b",
    ],
    "term_loan_a": [
        r"term\s+(?:loan\s+)?a\b",
        r"term\s+a\s+(?:loan|facility)",
        r"TLA\b",
        r"tranche\s+a\b",
    ],
    "term_loan": [
        r"term\s+(?:loan|facility)",
        r"term\s+credit\s+facility",
        r"senior\s+(?:secured\s+)?term\s+(?:loan|facility)",
    ],
    "delayed_draw": [
        r"delayed[\s-]+draw",
        r"DDTL\b",
        r"delayed\s+funding",
    ],
    "bridge": [
        r"bridge\s+(?:loan|facility|credit)",
        r"bridge\s+financing",
        r"interim\s+loan",
    ],
    "letter_of_credit": [
        r"letter\s+of\s+credit",
        r"L/?C\s+(?:facility|commitment|sub[\s-]?facility)",
        r"standby\s+letter",
    ],
    "swingline": [
        r"swing[\s-]?line",
        r"swingline\s+(?:loan|facility|commitment)",
    ],
    "incremental": [
        r"incremental\s+(?:term\s+)?(?:loan|facility|commitment)",
        r"accordion\s+(?:facility|feature)",
    ],
}

FACILITY_TYPE_PATTERNS = compile_patterns(FACILITY_TYPE_SYNONYMS)


# ═══════════════════════════════════════════════════════════════════════════
# DOLLAR AMOUNT patterns
# ═══════════════════════════════════════════════════════════════════════════

AMOUNT_PATTERNS: list[str] = [
    r"\$\s*([\d,]+(?:\.\d+)?)\s*(million|billion|mn|bn|MM|M)?",
    r"([\d,]+(?:\.\d+)?)\s*(?:USD|U\.S\.\s*(?:Dollars?|dollars?))",
    r"(?:GBP|EUR|£|€)\s*([\d,]+(?:\.\d+)?)\s*(million|billion|mn|bn|MM|M)?",
]

AMOUNT_MULTIPLIERS: dict[str, float] = {
    "million": 1_000_000,
    "mn": 1_000_000,
    "mm": 1_000_000,
    "m": 1_000_000,
    "billion": 1_000_000_000,
    "bn": 1_000_000_000,
}

CURRENCY_INDICATORS: dict[str, list[str]] = {
    "USD": [r"\$", r"USD", r"U\.S\.\s*[Dd]ollars?", r"United\s+States\s+[Dd]ollars?"],
    "GBP": [r"£", r"GBP", r"[Ss]terling", r"[Pp]ounds?\s+[Ss]terling"],
    "EUR": [r"€", r"EUR", r"[Ee]uro[s]?"],
    "CAD": [r"CAD", r"C\$", r"Canadian\s+[Dd]ollars?"],
    "AUD": [r"AUD", r"A\$", r"Australian\s+[Dd]ollars?"],
}


# ═══════════════════════════════════════════════════════════════════════════
# DATE patterns
# ═══════════════════════════════════════════════════════════════════════════

DATE_PATTERNS: list[str] = [
    # January 1, 2024  /  January 1 2024
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}",
    # Jan. 1, 2024  /  Sept. 30, 2024
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4}",
    # 1/1/2024  /  01/01/2024
    r"\d{1,2}/\d{1,2}/\d{4}",
    # 2024-01-01
    r"\d{4}-\d{2}-\d{2}",
    # 1 January 2024 (UK format)
    r"\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}",
]

DATE_RE = re.compile("|".join(f"(?:{p})" for p in DATE_PATTERNS), re.IGNORECASE)


# ═══════════════════════════════════════════════════════════════════════════
# MATURITY DATE patterns
# ═══════════════════════════════════════════════════════════════════════════

MATURITY_SYNONYMS: list[str] = [
    # Direct label patterns (prose + definitions)
    r"""["\u201c\u201d]?\s*(?:maturity\s+date|final\s+maturity\s+date|stated\s+maturity\s+date|termination\s+date|term\s+loan\s+maturity\s+date|revolving\s+(?:credit\s+)?(?:facility\s+)?maturity\s+date|revolving\s+termination\s+date)\s*["\u201c\u201d]?\s*[:)(\s]+""",
    # Prose patterns
    r"matures?\s+on\s+",
    r"shall\s+mature\s+on\s+",
    r"(?:loans?|facility|commitment)\s+(?:shall|will)\s+(?:terminate|expire|mature)\s+on\s+",
    r"(?:the\s+)?(?:final|last)\s+(?:scheduled\s+)?(?:payment|repayment|maturity)\s+date\s+(?:is|shall\s+be|being)\s+",
    r"terminat(?:es?|ing)\s+on\s+",
    r"expir(?:es?|ing)\s+on\s+",
]

MATURITY_RE = re.compile(
    r"(?:" + "|".join(f"(?:{p})" for p in MATURITY_SYNONYMS) + r")"
    r"(" + DATE_RE.pattern + r")",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════════════════
# EFFECTIVE DATE patterns
# ═══════════════════════════════════════════════════════════════════════════

EFFECTIVE_SYNONYMS: list[str] = [
    # Direct label patterns (prose + definitions)
    r"""["\u201c\u201d]?\s*(?:effective\s+date|closing\s+date|funding\s+date|settlement\s+date|initial\s+funding\s+date|initial\s+borrowing\s+date)\s*["\u201c\u201d]?\s*[:)(\s]+""",
    # Prose patterns
    r"dated\s+as\s+of\s+",
    r"entered\s+into\s+(?:as\s+of\s+)?",
    r"made\s+(?:and\s+entered\s+into\s+)?as\s+of\s+",
    r"executed\s+(?:as\s+of\s+|on\s+)",
    r"(?:this\s+)?agreement\s+(?:is\s+)?dated\s+(?:as\s+of\s+)?",
]

EFFECTIVE_RE = re.compile(
    r"(?:" + "|".join(f"(?:{p})" for p in EFFECTIVE_SYNONYMS) + r")"
    r"(" + DATE_RE.pattern + r")",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════════════════
# INTEREST RATE BENCHMARK patterns
# ═══════════════════════════════════════════════════════════════════════════

BENCHMARK_SYNONYMS: dict[str, list[str]] = {
    "Term SOFR": [
        r"Term\s+SOFR",
        r"Adjusted\s+Term\s+SOFR",
        r"CME\s+Term\s+SOFR",
    ],
    "SOFR": [
        r"\bSOFR\b",
        r"Secured\s+Overnight\s+Financing\s+Rate",
        r"Daily\s+(?:Simple\s+)?SOFR",
        r"Compounded\s+SOFR",
    ],
    "LIBOR": [
        r"\bLIBOR\b",
        r"London\s+Interbank\s+Offered\s+Rate",
        r"LIBO\s+Rate",
        r"Eurodollar\s+Rate",
        r"Adjusted\s+LIBO\s+Rate",
    ],
    "EURIBOR": [
        r"\bEURIBOR\b",
        r"Euro\s+Interbank\s+Offered\s+Rate",
    ],
    "Prime Rate": [
        r"Prime\s+Rate",
        r"Prime\s+Lending\s+Rate",
        r"Wall\s+Street\s+Journal\s+Prime",
        r"WSJ\s+Prime",
    ],
    "ABR": [
        r"\bABR\b",
        r"Alternate\s+Base\s+Rate",
        r"Alternate\s+Base\s+Rate\s+Loan",
    ],
    "Base Rate": [
        r"Base\s+Rate",
        r"Canadian\s+Base\s+Rate",
        r"Canadian\s+Prime\s+Rate",
        r"CB\s+Rate",
    ],
    "Federal Funds Rate": [
        r"Federal\s+Funds?\s+(?:Effective\s+)?Rate",
        r"Fed\s+Funds?\s+Rate",
    ],
    "SONIA": [
        r"\bSONIA\b",
        r"Sterling\s+Overnight\s+(?:Index\s+)?Average",
        r"Compounded\s+SONIA",
        r"Daily\s+SONIA",
    ],
    "BBSY": [
        r"\bBBSY\b",
        r"Bank\s+Bill\s+Swap\s+(?:Bid\s+)?Rate",
    ],
    "CDOR": [
        r"\bCDOR\b",
        r"Canadian\s+Dollar\s+Offered\s+Rate",
    ],
    "TIBOR": [
        r"\bTIBOR\b",
        r"Tokyo\s+Interbank\s+Offered\s+Rate",
    ],
}

BENCHMARK_PATTERNS = compile_patterns(BENCHMARK_SYNONYMS, flags=re.IGNORECASE)


# ═══════════════════════════════════════════════════════════════════════════
# SPREAD patterns
# ═══════════════════════════════════════════════════════════════════════════

SPREAD_SYNONYMS: list[str] = [
    r"(?:plus|add|\+)\s+(\d+(?:\.\d+)?)\s*%",
    r"(?:plus|add|\+)\s+(\d+(?:\.\d+)?)\s*(?:basis\s+points|bps|b\.p\.s\.)",
    r"(?:applicable\s+)?(?:margin|spread)\s+(?:of|equal\s+to|is|shall\s+be)\s+(\d+(?:\.\d+)?)\s*%",
    r"(?:applicable\s+)?(?:margin|spread)\s+(?:of|equal\s+to|is|shall\s+be)\s+(\d+(?:\.\d+)?)\s*(?:basis\s+points|bps)",
    r"(\d+(?:\.\d+)?)\s*%\s+per\s+annum\s+(?:above|over|in\s+excess\s+of)",
]


# ═══════════════════════════════════════════════════════════════════════════
# FLOOR patterns
# ═══════════════════════════════════════════════════════════════════════════

FLOOR_SYNONYMS: list[str] = [
    r"floor\s+of\s+(\d+(?:\.\d+)?)\s*%",
    r"floor\s+of\s+(\d+(?:\.\d+)?)\s*(?:basis\s+points|bps)",
    r"(?:shall|will)\s+(?:not\s+)?be\s+(?:less|lower)\s+than\s+(\d+(?:\.\d+)?)\s*%",
    r"(?:interest\s+rate|benchmark|SOFR|LIBOR)\s+floor",
    r"(?:minimum|floor)\s+(?:interest\s+)?rate\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%",
    r"(?:deemed\s+to\s+be|shall\s+be\s+deemed)\s+(\d+(?:\.\d+)?)\s*%",
    r"in\s+no\s+event\s+(?:shall|will)\s+.*?be\s+less\s+than\s+(\d+(?:\.\d+)?)\s*%",
]


# ═══════════════════════════════════════════════════════════════════════════
# PIK patterns
# ═══════════════════════════════════════════════════════════════════════════

PIK_SYNONYMS: list[str] = [
    r"\bPIK\b",
    r"paid?\s+in\s+kind",
    r"payment[\s-]+in[\s-]+kind",
    r"interest\s+(?:may\s+be\s+)?(?:paid|payable)\s+in\s+kind",
    r"capitalize[ds]?\s+interest",
    r"PIK\s+(?:interest|toggle|election|option)",
]


# ═══════════════════════════════════════════════════════════════════════════
# PARTY ROLE patterns
# ═══════════════════════════════════════════════════════════════════════════

PARTY_ROLE_SYNONYMS: dict[str, list[str]] = {
    "borrower": [
        r"(?:the\s+)?Borrower",
        r"(?:the\s+)?Co[\s-]?Borrower",
        r"(?:the\s+)?(?:Credit\s+)?(?:Party|Parties)",
        r"(?:the\s+)?Obligor",
        r"(?:the\s+)?Debtor",
    ],
    "lender": [
        r"(?:the\s+)?Lenders?",
        r"(?:the\s+)?(?:Initial\s+)?(?:Term\s+)?Lenders?",
        r"(?:the\s+)?Revolving\s+(?:Credit\s+)?Lenders?",
        r"(?:the\s+)?Banks?",
        r"(?:the\s+)?(?:Financial\s+)?Institutions?",
        r"(?:the\s+)?Noteholders?",
    ],
    "administrative_agent": [
        r"(?:the\s+)?Administrative\s+Agent",
        r"(?:the\s+)?(?:Facility\s+)?Agent",
        r"(?:the\s+)?Collateral\s+Agent",
        r"(?:the\s+)?Security\s+(?:Trustee|Agent)",
        r"(?:the\s+)?Paying\s+Agent",
    ],
    "guarantor": [
        r"(?:the\s+)?Guarantors?",
        r"(?:the\s+)?(?:Subsidiary\s+)?Guarantors?",
        r"(?:the\s+)?Guaranteeing\s+(?:Parties|Subsidiaries)",
        r"(?:the\s+)?Sureties",
    ],
    "arranger": [
        r"(?:the\s+)?(?:Joint\s+)?(?:Lead\s+)?Arrangers?",
        r"(?:the\s+)?(?:Joint\s+)?(?:Lead\s+)?(?:Book[\s-]?)?Runners?",
        r"(?:the\s+)?Mandated\s+Lead\s+Arrangers?",
        r"(?:the\s+)?(?:Global\s+)?Coordinators?",
        r"(?:the\s+)?Syndication\s+Agent",
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
# FINANCIAL COVENANT patterns
# ═══════════════════════════════════════════════════════════════════════════

FINANCIAL_COVENANT_SYNONYMS: dict[str, dict] = {
    "Maximum Leverage Ratio": {
        "metric": "leverage_ratio",
        "patterns": [
            r"(?:maximum\s+)?(?:total\s+)?leverage\s+ratio",
            r"(?:maximum\s+)?(?:consolidated\s+)?(?:total\s+)?(?:net\s+)?leverage\s+ratio",
            r"(?:total\s+)?(?:net\s+)?debt\s+to\s+(?:EBITDA|earnings)",
            r"(?:total\s+)?funded\s+debt\s+to\s+EBITDA",
            r"(?:consolidated\s+)?indebtedness\s+to\s+(?:EBITDA|earnings)",
        ],
    },
    "Minimum Interest Coverage Ratio": {
        "metric": "interest_coverage_ratio",
        "patterns": [
            r"(?:minimum\s+)?interest\s+coverage\s+ratio",
            r"(?:minimum\s+)?(?:consolidated\s+)?interest\s+coverage",
            r"EBITDA\s+to\s+(?:interest|interest\s+expense)",
            r"interest\s+expense\s+coverage",
        ],
    },
    "Minimum Fixed Charge Coverage Ratio": {
        "metric": "fixed_charge_coverage_ratio",
        "patterns": [
            r"(?:minimum\s+)?fixed\s+charge\s+coverage\s+ratio",
            r"(?:minimum\s+)?(?:consolidated\s+)?fixed\s+charge\s+coverage",
            r"FCCR",
        ],
    },
    "Maximum Senior Leverage Ratio": {
        "metric": "senior_leverage_ratio",
        "patterns": [
            r"(?:maximum\s+)?senior\s+(?:secured\s+)?leverage\s+ratio",
            r"(?:maximum\s+)?(?:first\s+lien|secured)\s+(?:net\s+)?leverage\s+ratio",
            r"senior\s+(?:secured\s+)?debt\s+to\s+EBITDA",
            r"first\s+lien\s+(?:net\s+)?leverage",
        ],
    },
    "Minimum Debt Service Coverage Ratio": {
        "metric": "debt_service_coverage_ratio",
        "patterns": [
            r"(?:minimum\s+)?debt\s+service\s+coverage\s+ratio",
            r"(?:minimum\s+)?(?:consolidated\s+)?debt\s+service\s+coverage",
            r"DSCR",
        ],
    },
    "Minimum Net Worth": {
        "metric": "net_worth",
        "patterns": [
            r"(?:minimum\s+)?(?:tangible\s+)?net\s+worth",
            r"(?:minimum\s+)?(?:consolidated\s+)?(?:tangible\s+)?net\s+worth",
            r"(?:minimum\s+)?stockholders?\s+equity",
            r"(?:minimum\s+)?shareholders?\s+equity",
        ],
    },
    "Maximum Capital Expenditures": {
        "metric": "capital_expenditures",
        "patterns": [
            r"(?:maximum\s+)?(?:consolidated\s+)?capital\s+expenditures?",
            r"(?:maximum\s+)?(?:consolidated\s+)?capex",
            r"(?:limitation\s+on\s+)?capital\s+expenditures?",
        ],
    },
    "Minimum EBITDA": {
        "metric": "minimum_ebitda",
        "patterns": [
            r"(?:minimum\s+)?(?:consolidated\s+)?(?:adjusted\s+)?EBITDA",
            r"(?:minimum\s+)?(?:trailing\s+)?(?:twelve|12)[\s-]?month\s+EBITDA",
        ],
    },
    "Minimum Liquidity": {
        "metric": "liquidity",
        "patterns": [
            r"(?:minimum\s+)?liquidity",
            r"(?:minimum\s+)?(?:unrestricted\s+)?cash\s+(?:and\s+cash\s+equivalents?)?",
            r"(?:minimum\s+)?available\s+(?:cash|liquidity)",
        ],
    },
    "Maximum Total Debt": {
        "metric": "total_debt",
        "patterns": [
            r"(?:maximum\s+)?(?:total\s+)?(?:consolidated\s+)?(?:funded\s+)?(?:indebtedness|debt)",
            r"(?:limitation\s+on\s+)?(?:total\s+)?indebtedness",
        ],
    },
}

# Build compiled patterns for financial covenants
FINANCIAL_COVENANT_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = []
for name, info in FINANCIAL_COVENANT_SYNONYMS.items():
    combined = "|".join(f"(?:{p})" for p in info["patterns"])
    FINANCIAL_COVENANT_PATTERNS.append(
        (name, info["metric"], re.compile(combined, re.IGNORECASE))
    )


# ═══════════════════════════════════════════════════════════════════════════
# NEGATIVE COVENANT patterns
# ═══════════════════════════════════════════════════════════════════════════

NEGATIVE_COVENANT_SYNONYMS: dict[str, list[str]] = {
    "Limitation on Liens": [
        r"\bliens?\b",
        r"\bsecurity\s+interests?\b",
        r"\bencumbrances?\b",
        r"\bpledges?\b",
    ],
    "Limitation on Indebtedness": [
        r"\bindebtedness\b",
        r"\bborrowing[s]?\b",
        r"\bdebt\s+incurrence\b",
    ],
    "Restricted Payments": [
        r"\brestricted\s+payments?\b",
        r"\brestricted\s+distributions?\b",
    ],
    "Limitation on Dividends": [
        r"\bdividends?\b",
        r"\bdistributions?\s+to\s+(?:equity\s+)?holders?\b",
        r"\bshareholder\s+distributions?\b",
    ],
    "Limitation on Asset Sales": [
        r"\basset\s+sales?\b",
        r"\bdispositions?\b",
        r"\bsale\s+of\s+(?:assets?|propert)",
        r"\btransfer\s+of\s+assets?\b",
    ],
    "Limitation on Investments": [
        r"\binvestments?\b",
        r"\bacquisitions?\b",
        r"\bpermitted\s+investments?\b",
    ],
    "Limitation on Mergers": [
        r"\bmergers?\b",
        r"\bconsolid",
        r"\bamalgamations?\b",
        r"\bfundamental\s+changes?\b",
    ],
    "Limitation on Transactions with Affiliates": [
        r"\baffiliate\s+transactions?\b",
        r"\btransactions?\s+with\s+affiliates?\b",
        r"\brelated[\s-]party\s+transactions?\b",
    ],
    "Limitation on Restrictive Agreements": [
        r"\brestrictive\s+agreements?\b",
        r"\bnegative\s+pledge\b",
        r"\banti[\s-]layering\b",
    ],
    "Limitation on Sale-Leaseback": [
        r"\bsale[\s-]?leaseback\b",
        r"\bsale\s+and\s+leaseback\b",
    ],
    "Limitation on Line of Business": [
        r"\bline\s+of\s+business\b",
        r"\bchange\s+in\s+(?:nature\s+of\s+)?business\b",
        r"\bfundamental\s+change\s+(?:in|of)\s+business\b",
    ],
}

NEGATIVE_COVENANT_PATTERNS = compile_patterns(NEGATIVE_COVENANT_SYNONYMS)


# ═══════════════════════════════════════════════════════════════════════════
# AFFIRMATIVE COVENANT patterns
# ═══════════════════════════════════════════════════════════════════════════

AFFIRMATIVE_COVENANT_SYNONYMS: dict[str, list[str]] = {
    "Financial Reporting": [
        r"\bfinancial\s+(?:statements?|reports?|reporting)\b",
        r"\bannual\s+(?:audited\s+)?(?:financial\s+)?(?:statements?|reports?)\b",
        r"\bquarterly\s+(?:financial\s+)?(?:statements?|reports?)\b",
        r"\bcompliance\s+certificates?\b",
    ],
    "Insurance": [
        r"\binsurance\b",
        r"\bmaintain\s+insurance\b",
    ],
    "Compliance with Laws": [
        r"\bcompliance\s+with\s+laws?\b",
        r"\bcompliance\s+with\s+(?:applicable\s+)?(?:law|regulation)",
    ],
    "Maintenance of Properties": [
        r"\bmaintenance\s+of\s+propert",
        r"\bpreservation\s+of\s+(?:assets?|propert)",
    ],
    "Books and Records": [
        r"\bbooks\s+and\s+records?\b",
        r"\baccounting\s+records?\b",
        r"\bmaintain\s+(?:proper\s+)?books\b",
    ],
    "Notices": [
        r"\bnotices?\b",
        r"\bnotification\s+(?:of\s+)?(?:default|event)",
    ],
    "Use of Proceeds": [
        r"\buse\s+of\s+proceeds?\b",
        r"\bapplication\s+of\s+proceeds?\b",
    ],
    "Payment of Taxes": [
        r"\bpayment\s+of\s+(?:taxes?|obligations?)\b",
        r"\btax(?:es)?\s+and\s+(?:other\s+)?(?:claims?|obligations?)\b",
    ],
    "Corporate Existence": [
        r"\bcorporate\s+existence\b",
        r"\bpreservation\s+of\s+(?:corporate\s+)?existence\b",
        r"\bmaintain\s+(?:its\s+)?(?:corporate\s+)?(?:existence|organization)\b",
    ],
    "Inspection Rights": [
        r"\binspection\s+(?:rights?|obligations?)\b",
        r"\baccess\s+to\s+(?:propert|books|records)",
        r"\bvisitation\s+rights?\b",
    ],
    "Environmental Compliance": [
        r"\benvironmental\s+(?:compliance|laws?|matters?|regulations?)\b",
    ],
    "Anti-Corruption": [
        r"\banti[\s-]?corruption\b",
        r"\bFCPA\b",
        r"\banti[\s-]?bribery\b",
    ],
}

AFFIRMATIVE_COVENANT_PATTERNS = compile_patterns(AFFIRMATIVE_COVENANT_SYNONYMS)


# ═══════════════════════════════════════════════════════════════════════════
# AMENDMENT DETECTION patterns
# ═══════════════════════════════════════════════════════════════════════════

AMENDMENT_DETECTION_SYNONYMS: list[str] = [
    r"(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|\d+(?:st|nd|rd|th)?)\s+Amendment",
    r"Amended\s+and\s+Restated",
    r"Amendment\s+(?:No\.|Number|#)\s*\d+",
    r"Amendment\s+to\s+(?:the\s+)?(?:Credit|Loan|Facility)\s+Agreement",
    r"Modification\s+Agreement",
    r"Waiver\s+and\s+(?:Amendment|Modification)",
    r"Consent\s+and\s+Amendment",
    r"(?:Omnibus|Incremental)\s+Amendment",
    r"Restatement\s+Agreement",
    r"Supplemental\s+(?:Indenture|Agreement)",
]

AMENDMENT_ORDINALS: dict[str, str] = {
    "first": "1", "1st": "1",
    "second": "2", "2nd": "2",
    "third": "3", "3rd": "3",
    "fourth": "4", "4th": "4",
    "fifth": "5", "5th": "5",
    "sixth": "6", "6th": "6",
    "seventh": "7", "7th": "7",
    "eighth": "8", "8th": "8",
    "ninth": "9", "9th": "9",
    "tenth": "10", "10th": "10",
    "eleventh": "11", "11th": "11",
    "twelfth": "12", "12th": "12",
}


# ═══════════════════════════════════════════════════════════════════════════
# CALL PROTECTION patterns
# ═══════════════════════════════════════════════════════════════════════════

CALL_PROTECTION_SYNONYMS: list[str] = [
    r"call\s+protection",
    r"prepayment\s+premium",
    r"make[\s-]?whole",
    r"soft\s+call",
    r"hard\s+call",
    r"non[\s-]?call",
    r"no[\s-]?call",
    r"prepayment\s+penalty",
    r"redemption\s+premium",
    r"yield\s+maintenance",
    r"early\s+repayment\s+(?:fee|charge|premium)",
    r"repricing\s+protection",
    r"repricing\s+premium",
]


# ═══════════════════════════════════════════════════════════════════════════
# TICKING FEE patterns
# ═══════════════════════════════════════════════════════════════════════════

TICKING_FEE_SYNONYMS: list[str] = [
    r"ticking\s+fee",
    r"delayed[\s-]?draw\s+fee",
    r"commitment\s+ticking\s+fee",
    r"undrawn\s+(?:commitment\s+)?fee",
    r"availability\s+fee",
]


# ═══════════════════════════════════════════════════════════════════════════
# RATIO patterns (for covenant thresholds)
# ═══════════════════════════════════════════════════════════════════════════

RATIO_PATTERNS: list[str] = [
    r"(\d+\.\d+)\s*(?:to|:)\s*1\.0?0?",
    r"(\d+\.\d+)\s*x\b",
    r"(\d+\.\d+)\s*(?:to|:)\s*(\d+\.\d+)",
]


# ═══════════════════════════════════════════════════════════════════════════
# TESTING FREQUENCY patterns
# ═══════════════════════════════════════════════════════════════════════════

TESTING_FREQUENCY_SYNONYMS: dict[str, list[str]] = {
    "quarterly": [
        r"\bquarter(?:ly)?\b",
        r"\beach\s+fiscal\s+quarter\b",
        r"\blast\s+(?:day|date)\s+of\s+each\s+(?:fiscal\s+)?quarter\b",
    ],
    "annual": [
        r"\bannual(?:ly)?\b",
        r"\bfiscal\s+year[\s-]?end\b",
        r"\beach\s+fiscal\s+year\b",
    ],
    "monthly": [
        r"\bmonth(?:ly)?\b",
        r"\beach\s+(?:calendar\s+)?month\b",
    ],
    "semi-annual": [
        r"\bsemi[\s-]?annual(?:ly)?\b",
        r"\btwice\s+(?:per|each|a)\s+year\b",
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
# SECTION HEADER patterns (for section_detector)
# ═══════════════════════════════════════════════════════════════════════════

SECTION_HEADER_PATTERNS: dict[str, list[str]] = {
    "article_roman": [
        r"^\s*ARTICLE\s+([IVXLCDM]+)\b[.\s]*(.*)",
    ],
    "article_arabic": [
        r"^\s*ARTICLE\s+(\d+)\b[.\s]*(.*)",
    ],
    "section_dotted": [
        r"^\s*(?:SECTION|Section)\s+(\d+\.\d+)\b[.\s]*(.*)",
    ],
    "section_loose": [
        r"^\s*(\d{1,3}\.\d{1,3})\s{2,}([A-Z].*)",
    ],
    "part": [
        r"^\s*PART\s+([IVXLCDM]+|\d+)\b[.\s]*(.*)",
    ],
    "clause": [
        r"^\s*(?:CLAUSE|Clause)\s+(\d+(?:\.\d+)?)\b[.\s]*(.*)",
    ],
    "schedule": [
        r"^\s*(?:SCHEDULE|EXHIBIT|ANNEX)\s+([A-Z\d]+)\b[.\s]*(.*)",
    ],
}
