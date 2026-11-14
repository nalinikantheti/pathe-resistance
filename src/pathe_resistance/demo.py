"""Small synthetic fixtures created locally. No API calls, imagery or model downloads."""

import json
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import LineString, box

from .pipeline import run


def create_demo(directory):
    """Create a short exposed path and a longer tree-adjacent alternative."""
    directory = Path(directory).resolve()
    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError("Choose an empty directory for the synthetic demo")
    directory.mkdir(parents=True, exist_ok=True)
    coords = {
        1: (50, 100),
        2: (150, 100),
        3: (250, 100),
        4: (50, 200),
        5: (150, 200),
        6: (250, 200),
    }
    graph = nx.MultiDiGraph(crs="EPSG:3857", synthetic=True)
    for node, (x, y) in coords.items():
        graph.add_node(node, x=float(x), y=float(y))
    for i, (u, v) in enumerate([(1, 2), (2, 3), (1, 4), (4, 5), (5, 6), (6, 3)]):
        line = LineString([coords[u], coords[v]])
        for a, b in [(u, v), (v, u)]:
            graph.add_edge(
                a,
                b,
                key=0,
                length=float(line.length),
                osmid=i + 1,
                geometry=LineString([coords[a], coords[b]]),
            )
    ox.io.save_graphml(graph, directory / "input.graphml")
    boundary = gpd.GeoDataFrame(
        {"label": ["Synthetic example; not a real neighborhood"]},
        geometry=[box(0, 50, 300, 250)],
        crs=3857,
    )
    boundary.to_crs(4326).to_file(directory / "boundary.geojson", driver="GeoJSON")
    rows, cols = np.indices((60, 80))
    x, y = (cols + 0.5) * 5, 300 - (rows + 0.5) * 5
    trees = ((y >= 125) | (abs(x - 50) <= 15) | (abs(x - 250) <= 15)).astype("uint8")
    with rasterio.open(
        directory / "trees.tif",
        "w",
        driver="GTiff",
        width=80,
        height=60,
        count=1,
        dtype="uint8",
        crs=3857,
        transform=from_origin(0, 300, 5, 5),
        nodata=255,
    ) as dst:
        dst.write(trees, 1)
        dst.update_tags(source="Synthetic demo only; no AI inference performed")
    config = {
        "boundary": "boundary.geojson",
        "graph": "input.graphml",
        "buffer_m": 0,
        "rasters": {"tree_cover": {"path": "trees.tif", "mode": "binary", "buffer_m": 10}},
        "model": {"canopy_weight": 2},
        "routes": [{"origin": 1, "destination": 3}],
        "output": "results",
    }
    path = directory / "config.json"
    path.write_text(json.dumps(config, indent=2) + "\n")
    return path


def run_demo(directory, *, include_map=False):
    """Exercise the same public pipeline as a real project with synthetic data."""
    path = create_demo(directory)
    if include_map:
        config = json.loads(path.read_text())
        config["map"] = True
        path.write_text(json.dumps(config, indent=2) + "\n")
    return run(path)
