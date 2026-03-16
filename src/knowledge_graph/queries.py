"""Utility queries over credit agreement knowledge graphs."""

import networkx as nx


def get_nodes_by_type(G: nx.DiGraph, node_type: str) -> list[tuple[str, dict]]:
    """Return all nodes of a given type."""
    return [(n, d) for n, d in G.nodes(data=True) if d.get("node_type") == node_type]


def get_facilities(G: nx.DiGraph) -> list[dict]:
    """Return all facility nodes with their attributes."""
    return [d for _, d in get_nodes_by_type(G, "Facility")]


def get_covenants(G: nx.DiGraph) -> list[dict]:
    """Return all covenant nodes."""
    return [d for _, d in get_nodes_by_type(G, "Covenant")]


def get_parties_for_facility(G: nx.DiGraph, facility_node_id: str) -> list[dict]:
    """Return all parties connected to a facility."""
    result = []
    for pred in G.predecessors(facility_node_id):
        edge_data = G.edges[pred, facility_node_id]
        node_data = G.nodes[pred]
        if node_data.get("node_type") == "Party":
            result.append({**node_data, "relationship": edge_data.get("edge_type", "")})
    return result


def get_thresholds_for_covenant(G: nx.DiGraph, covenant_node_id: str) -> list[dict]:
    """Return thresholds connected to a covenant."""
    result = []
    for succ in G.successors(covenant_node_id):
        edge_data = G.edges[covenant_node_id, succ]
        if edge_data.get("edge_type") == "HAS_THRESHOLD":
            result.append(G.nodes[succ])
    return result


def graph_summary(G: nx.DiGraph) -> dict:
    """Return summary statistics for the graph."""
    type_counts = {}
    for _, d in G.nodes(data=True):
        t = d.get("node_type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    edge_type_counts = {}
    for _, _, d in G.edges(data=True):
        t = d.get("edge_type", "unknown")
        edge_type_counts[t] = edge_type_counts.get(t, 0) + 1

    return {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "node_types": type_counts,
        "edge_types": edge_type_counts,
    }
