import geopandas as gpd
import networkx as nx
import osmnx as ox
import pytest
from shapely.geometry import box

from pathe_resistance.graph import (
    extract_walking_graph,
    graph_summary,
    read_boundary,
    routing_polygon,
)


def test_download_keeps_all_components_and_restores_settings(monkeypatch, tmp_path):
    boundary = gpd.GeoDataFrame(geometry=[box(0, 0, 100, 100)], crs=3857).to_crs(4326)
    graph = nx.MultiDiGraph()
    graph.add_edge(1, 2)
    graph.add_node(3)
    previous = ox.settings.cache_folder

    def fetch(polygon, **options):
        assert options["network_type"] == "walk"
        assert options["retain_all"] is True
        assert ox.settings.cache_folder == tmp_path
        return graph

    monkeypatch.setattr(ox.graph, "graph_from_polygon", fetch)
    result = extract_walking_graph(boundary, buffer_m=100, cache_folder=tmp_path)
    assert ox.settings.cache_folder == previous
    assert graph_summary(result)["weak_components"] == 2
    original = boundary.geometry.union_all()
    assert routing_polygon(boundary, 100).area > original.area


def test_point_boundary_is_rejected(tmp_path):
    from shapely.geometry import Point

    path = tmp_path / "point.geojson"
    gpd.GeoDataFrame(geometry=[Point(0, 0)], crs=4326).to_file(path, driver="GeoJSON")
    with pytest.raises(ValueError, match="polygons"):
        read_boundary(path)
