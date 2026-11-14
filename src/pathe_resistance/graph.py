"""Boundary-based OSM extraction with all components retained by default."""

from pathlib import Path

import geopandas as gpd
import networkx as nx
import osmnx as ox
from pyproj import CRS


def metric_crs(frame):
    """Choose a local metric CRS; preserve a suitable existing projected CRS."""
    if frame.crs is None:
        raise ValueError("Input geometries must declare their CRS")
    crs = CRS(frame.crs)
    if crs.is_projected and all(a.unit_conversion_factor == 1 for a in crs.axis_info):
        return crs
    estimated = frame.estimate_utm_crs()
    if estimated is None:
        raise ValueError("Could not choose a metric CRS; reproject inputs explicitly")
    return estimated


def read_boundary(path):
    boundary = gpd.read_file(path)
    if boundary.empty or boundary.crs is None:
        raise ValueError("Boundary must be nonempty and have a declared CRS")
    if boundary.geometry.isna().any() or boundary.geometry.is_empty.any():
        raise ValueError("Boundary has missing or empty geometry")
    if not boundary.geometry.is_valid.all():
        raise ValueError("Repair invalid boundary geometry before extraction")
    if not boundary.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError("Boundary must contain polygons")
    return boundary.to_crs(4326)


def routing_polygon(boundary, buffer_m=500):
    """Buffer in meters before converting back to geographic coordinates."""
    from math import isfinite

    if not isfinite(buffer_m) or buffer_m < 0:
        raise ValueError("buffer_m must be finite and nonnegative")
    metric = boundary.to_crs(metric_crs(boundary))
    polygon = metric.geometry.union_all().buffer(buffer_m)
    return gpd.GeoSeries([polygon], crs=metric.crs).to_crs(4326).iloc[0]


def extract_walking_graph(boundary, *, buffer_m=500, cache_folder=None):
    """Download a walk-filtered graph. A boundary is a GeoDataFrame or file path.

    OSM walking eligibility does not validate entrances, crossings or legal access.
    A buffer reduces boundary effects but is not a route-completeness certificate.
    """
    if isinstance(boundary, (str, Path)):
        boundary = read_boundary(boundary)
    polygon = routing_polygon(boundary, buffer_m)
    previous_cache = ox.settings.cache_folder
    previous_use_cache = ox.settings.use_cache
    try:
        if cache_folder is not None:
            ox.settings.cache_folder = Path(cache_folder)
        ox.settings.use_cache = True
        graph = ox.graph.graph_from_polygon(
            polygon,
            network_type="walk",
            simplify=True,
            retain_all=True,
            truncate_by_edge=True,
        )
    finally:
        ox.settings.cache_folder = previous_cache
        ox.settings.use_cache = previous_use_cache
    graph.graph["attribution"] = "© OpenStreetMap contributors; ODbL"
    return graph


def graph_summary(graph):
    sizes = sorted((len(c) for c in nx.weakly_connected_components(graph)), reverse=True)
    return {
        "nodes": graph.number_of_nodes(),
        "directed_edges": graph.number_of_edges(),
        "weak_components": len(sizes),
        "largest_component_nodes": sizes[0] if sizes else 0,
    }
