import networkx as nx
import pytest

from pathe_resistance import shortest_route, supported_graph


def test_keeps_parallel_edge_and_direction():
    graph = nx.MultiDiGraph()
    graph.add_edge(1, 2, key=4, resistance_s=10, baseline_s=8, length=10)
    graph.add_edge(1, 2, key=9, resistance_s=3, baseline_s=2, length=3)
    route = shortest_route(graph, 1, 2)
    assert route.edges == ((1, 2, 9),)
    assert route.objective_cost == 3
    with pytest.raises(nx.NetworkXNoPath):
        shortest_route(graph, 2, 1)


def test_missing_weight_never_silently_defaults_to_one():
    graph = nx.MultiDiGraph()
    graph.add_edge(1, 2, length=100, baseline_s=80)
    with pytest.raises(ValueError, match="routing attributes"):
        shortest_route(graph, 1, 2)
    supported = supported_graph(graph)
    assert supported.number_of_edges() == 0
    assert graph.number_of_edges() == 1


def test_negative_weights_are_errors():
    graph = nx.MultiDiGraph()
    graph.add_edge(1, 2, resistance_s=-1)
    with pytest.raises(ValueError):
        supported_graph(graph)


def test_same_origin_has_zero_cost():
    graph = nx.MultiDiGraph()
    graph.add_node(1)
    assert shortest_route(graph, 1, 1).objective_cost == 0
