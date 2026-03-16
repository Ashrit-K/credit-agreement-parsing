"""NetworkX node/edge type definitions for credit agreement knowledge graphs."""

# Node types
NODE_TYPES = {
    "Document": {"attrs": ["doc_id", "title", "agreement_date", "file_name"]},
    "Party": {"attrs": ["name", "role"]},
    "Facility": {"attrs": ["facility_type", "name", "amount", "currency", "maturity_date"]},
    "InterestTerms": {"attrs": ["rate_type", "benchmark", "spread_bps", "floor_pct"]},
    "Covenant": {"attrs": ["covenant_type", "name", "metric", "testing_frequency"]},
    "Threshold": {"attrs": ["period", "value"]},
    "Amendment": {"attrs": ["amendment_number", "amendment_date", "summary_of_changes"]},
}

# Edge types: (source_type, edge_label, target_type)
EDGE_TYPES = [
    ("Document", "HAS_PARTY", "Party"),
    ("Document", "HAS_FACILITY", "Facility"),
    ("Document", "HAS_COVENANT", "Covenant"),
    ("Document", "HAS_AMENDMENT", "Amendment"),
    ("Facility", "HAS_INTEREST_TERMS", "InterestTerms"),
    ("Covenant", "HAS_THRESHOLD", "Threshold"),
    ("Amendment", "AMENDS", "Document"),
    ("Party", "BORROWS_UNDER", "Facility"),
    ("Party", "LENDS_UNDER", "Facility"),
    ("Party", "AGENT_FOR", "Facility"),
]


def node_id(node_type: str, **kwargs) -> str:
    """Generate a deterministic node ID from type and key attributes."""
    parts = [node_type]
    for k, v in sorted(kwargs.items()):
        parts.append(f"{k}={v}")
    return ":".join(parts)
