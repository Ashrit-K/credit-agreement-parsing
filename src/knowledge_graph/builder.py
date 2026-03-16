"""Builds per-document NetworkX DiGraph from parsed CreditAgreementDocument."""

import json
from pathlib import Path

import networkx as nx

from src.models.schema import CreditAgreementDocument
from src.models.graph_ontology import node_id, NODE_TYPES


def build_graph(doc: CreditAgreementDocument) -> nx.DiGraph:
    """Build a knowledge graph from a parsed credit agreement document."""
    G = nx.DiGraph()

    # Document node
    doc_nid = node_id("Document", doc_id=doc.doc_id)
    G.add_node(doc_nid, node_type="Document", doc_id=doc.doc_id,
               title=doc.title, agreement_date=doc.agreement_date,
               file_name=doc.file_name)

    # Party nodes
    for party in doc.parties:
        p_nid = node_id("Party", name=party.name, role=party.role)
        G.add_node(p_nid, node_type="Party", name=party.name, role=party.role,
                   provenance=party.source_ref.provenance_id if party.source_ref else "")
        G.add_edge(doc_nid, p_nid, edge_type="HAS_PARTY")

    # Facility nodes
    for i, facility in enumerate(doc.facilities):
        f_nid = node_id("Facility", doc_id=doc.doc_id, idx=str(i))
        G.add_node(f_nid, node_type="Facility", facility_type=facility.facility_type,
                   name=facility.name, amount=facility.amount,
                   currency=facility.currency, maturity_date=facility.maturity_date,
                   provenance=facility.source_ref.provenance_id if facility.source_ref else "")
        G.add_edge(doc_nid, f_nid, edge_type="HAS_FACILITY")

        # Interest terms
        if facility.interest_terms:
            it = facility.interest_terms
            it_nid = node_id("InterestTerms", doc_id=doc.doc_id, facility_idx=str(i))
            G.add_node(it_nid, node_type="InterestTerms", rate_type=it.rate_type,
                       benchmark=it.benchmark, spread_bps=it.spread_bps,
                       floor_pct=it.floor_pct,
                       provenance=it.source_ref.provenance_id if it.source_ref else "")
            G.add_edge(f_nid, it_nid, edge_type="HAS_INTEREST_TERMS")

        # Link parties to facilities
        for party in doc.parties:
            p_nid = node_id("Party", name=party.name, role=party.role)
            if party.role in ("borrower",):
                G.add_edge(p_nid, f_nid, edge_type="BORROWS_UNDER")
            elif party.role in ("lender",):
                G.add_edge(p_nid, f_nid, edge_type="LENDS_UNDER")
            elif party.role in ("administrative_agent", "agent"):
                G.add_edge(p_nid, f_nid, edge_type="AGENT_FOR")

    # Covenant nodes
    for i, covenant in enumerate(doc.covenants):
        c_nid = node_id("Covenant", doc_id=doc.doc_id, idx=str(i))
        G.add_node(c_nid, node_type="Covenant", covenant_type=covenant.covenant_type,
                   name=covenant.name, metric=covenant.metric,
                   testing_frequency=covenant.testing_frequency,
                   provenance=covenant.source_ref.provenance_id if covenant.source_ref else "")
        G.add_edge(doc_nid, c_nid, edge_type="HAS_COVENANT")

        # Thresholds
        for j, threshold in enumerate(covenant.thresholds):
            t_nid = node_id("Threshold", doc_id=doc.doc_id, covenant_idx=str(i), idx=str(j))
            G.add_node(t_nid, node_type="Threshold", period=threshold.period,
                       value=threshold.value,
                       provenance=threshold.source_ref.provenance_id if threshold.source_ref else "")
            G.add_edge(c_nid, t_nid, edge_type="HAS_THRESHOLD")

    # Amendment nodes
    for i, amendment in enumerate(doc.amendments):
        a_nid = node_id("Amendment", doc_id=doc.doc_id, idx=str(i))
        G.add_node(a_nid, node_type="Amendment", amendment_number=amendment.amendment_number,
                   amendment_date=amendment.amendment_date,
                   summary_of_changes=amendment.summary_of_changes,
                   provenance=amendment.source_ref.provenance_id if amendment.source_ref else "")
        G.add_edge(doc_nid, a_nid, edge_type="HAS_AMENDMENT")

    return G


def export_graph_json(G: nx.DiGraph, output_path: Path) -> None:
    """Export graph as node-link JSON."""
    data = nx.node_link_data(G)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def export_graph_gexf(G: nx.DiGraph, output_path: Path) -> None:
    """Export graph as GEXF (for Gephi / Neo4j import)."""
    # Convert all attributes to strings for GEXF compatibility
    G_copy = G.copy()
    for _, attrs in G_copy.nodes(data=True):
        for k, v in list(attrs.items()):
            if v is None:
                attrs[k] = ""
            else:
                attrs[k] = str(v)
    nx.write_gexf(G_copy, str(output_path))
