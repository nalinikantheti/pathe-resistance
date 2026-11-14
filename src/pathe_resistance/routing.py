"""Route on explicit finite weights, retaining parallel-edge identities."""

from dataclasses import dataclass
from math import isfinite

import networkx as nx


@dataclass(frozen=True)
class Route:
    nodes: tuple
    edges: tuple  # (u, v, key), in traversal order
    distance_m: float
    walking_seconds: float
    objective_cost: float
    weight: str


def supported_graph(graph, weight="resistance_s"):
    """Return a copy with unsupported edges removed; do not connect components."""
    result = graph.copy()
    invalid = []
    for u, v, key, data in result.edges(keys=True, data=True):
        try:
            value = float(data[weight])
        except (KeyError, TypeError, ValueError):
            invalid.append((u, v, key))
            continue
        if not isfinite(value):
            invalid.append((u, v, key))
        elif value < 0:
            raise ValueError(f"Negative route weight on {(u, v, key)}")
        else:
            data[weight] = value
    result.remove_edges_from(invalid)
    result.graph["unsupported_edges_removed"] = len(invalid)
    return result


def shortest_route(graph, origin, destination, weight="resistance_s"):
    """Return exact chosen edge IDs; missing weights raise instead of defaulting to 1.

    Raises NetworkXNoPath/NodeNotFound when the requested trip is unavailable.
    Origin/destination are graph IDs. Coordinate snapping and entrance validation
    are intentionally caller decisions.
    """
    if not graph.is_directed() or not graph.is_multigraph():
        raise ValueError("Expected a directed MultiDiGraph")
    for u, v, key, data in graph.edges(keys=True, data=True):
        try:
            value = float(data[weight])
            length = float(data["length"])
            baseline = float(data["baseline_s"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Missing/invalid routing attributes on {(u, v, key)}") from exc
        if not all(isfinite(x) and x >= 0 for x in [value, length, baseline]):
            raise ValueError(f"Nonfinite/negative routing attributes on {(u, v, key)}")
        if not isinstance(data[weight], (int, float)):
            raise ValueError("Route weights must be numeric; use supported_graph after loading")
    path = nx.shortest_path(graph, origin, destination, weight=weight)
    chosen = []
    distance = time = cost = 0.0
    for u, v in zip(path, path[1:]):
        key, data = min(graph[u][v].items(), key=lambda item: item[1][weight])
        chosen.append((u, v, key))
        distance += float(data["length"])
        time += float(data["baseline_s"])
        cost += float(data[weight])
    return Route(tuple(path), tuple(chosen), distance, time, cost, weight)
