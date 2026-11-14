"""Configuration-driven graph → raster features → costs → route comparisons."""

import json
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import geopandas as gpd
import networkx as nx
import osmnx as ox
import pandas as pd

from .costs import ResistanceModel, apply_resistance
from .graph import extract_walking_graph, graph_summary, read_boundary
from .raster import sample_corridors
from .routing import shortest_route, supported_graph

ARTIFACTS = [
    "walking.graphml",
    "supported.graphml",
    "edges.gpkg",
    "edges.csv",
    "nodes.csv",
    "routes.geojson",
    "route_comparison.json",
    "manifest.json",
    "map.html",
]


def _path(base, value):
    return (base / Path(value)).resolve()


def run(config_path, *, overwrite=False):
    """Run a JSON configuration. All relative paths resolve beside the config.

    Overwrite replaces only documented artifacts, never source data. The return
    value is the manifest dictionary. All network operations are explicit: only
    the absence of a supplied GraphML triggers OSM extraction.
    """
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text())
    allowed = {
        "boundary",
        "graph",
        "buffer_m",
        "rasters",
        "model",
        "edge_features",
        "routes",
        "output",
        "map",
    }
    unknown = set(config) - allowed
    if unknown:
        raise ValueError(f"Unknown configuration keys: {sorted(unknown)}")
    if "output" not in config or not (config.get("graph") or config.get("boundary")):
        raise ValueError("Configuration needs output and either graph or boundary")
    base = config_path.parent
    output = _path(base, config["output"])
    source_paths = [config_path]
    for key in ["graph", "boundary", "edge_features"]:
        if config.get(key):
            source_paths.append(_path(base, config[key]))
    source_paths += [_path(base, spec["path"]) for spec in config.get("rasters", {}).values()]
    # Never replace a source with an artifact, even if --overwrite was requested.
    if any(output / name in source_paths for name in ARTIFACTS):
        raise ValueError("Output artifacts must not overwrite input files")
    if output.exists() and any(output.iterdir()) and not overwrite:
        raise FileExistsError(
            f"Output is not empty: {output}. Choose a new directory or --overwrite"
        )
    model = ResistanceModel(**config.get("model", {}))
    boundary = read_boundary(_path(base, config["boundary"])) if config.get("boundary") else None
    if config.get("graph"):
        graph = ox.io.load_graphml(_path(base, config["graph"]))
    else:
        graph = extract_walking_graph(
            boundary,
            buffer_m=config.get("buffer_m", 500),
            cache_folder=output / "osm_cache",
        )
    if graph.number_of_edges() == 0:
        raise ValueError("No graph edges found")
    nodes, edges = ox.convert.graph_to_gdfs(graph)
    edges = edges.reset_index()
    for name, spec in config.get("rasters", {}).items():
        if name not in {"tree_cover", "heat", "traffic"}:
            raise ValueError(f"Unknown raster feature {name}; expected tree_cover, heat or traffic")
        spec = dict(spec)
        raster_path = _path(base, spec.pop("path"))
        edges = sample_corridors(edges, raster_path, name=name, **spec)
    if config.get("edge_features"):
        extra = pd.read_csv(_path(base, config["edge_features"]))
        ids = ["u", "v", "key"]
        if not set(ids).issubset(extra.columns) or extra.duplicated(ids).any():
            raise ValueError("edge_features needs unique (u,v,key) columns")
        if extra[ids].isna().any().any():
            raise ValueError("edge_features IDs must not be missing")
        new_columns = [c for c in extra if c not in ids]
        collisions = set(new_columns).intersection(edges.columns)
        if collisions:
            raise ValueError(f"edge_features would overwrite columns: {sorted(collisions)}")
        known_ids = pd.MultiIndex.from_frame(edges[ids])
        if not pd.MultiIndex.from_frame(extra[ids]).isin(known_ids).all():
            raise ValueError("edge_features contains edge IDs absent from the graph")
        edges = edges.merge(extra, on=ids, how="left", validate="one_to_one")
    edges = apply_resistance(edges, model)
    for row in edges.itertuples(index=False):
        data = graph[row.u][row.v][row.key]
        for column in ["tree_cover", "heat", "traffic", "baseline_s", "resistance_s"] + [
            c for c in edges if c.endswith("_coverage") or c.endswith("_observed")
        ]:
            if hasattr(row, column):
                data[column] = float(getattr(row, column))
    supported = supported_graph(graph)
    comparisons, route_rows = [], []
    for i, pair in enumerate(config.get("routes", [])):
        origin, destination = pair["origin"], pair["destination"]
        record = {"pair": i, "origin": origin, "destination": destination}
        try:
            full_baseline = shortest_route(graph, origin, destination, "baseline_s")
            record["full_network_baseline"] = asdict(full_baseline)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            record["full_network_baseline"] = None
        try:
            baseline = shortest_route(supported, origin, destination, "baseline_s")
            selected = shortest_route(supported, origin, destination, "resistance_s")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            record["status"] = "unreachable_on_supported_graph"
            comparisons.append(record)
            continue
        record.update(status="ok", baseline=asdict(baseline), resistance=asdict(selected))
        base_resistance = sum(supported[u][v][key]["resistance_s"] for u, v, key in baseline.edges)
        record["baseline_resistance_s"] = base_resistance
        if selected.objective_cost > base_resistance + 1e-6:
            raise AssertionError(
                "Resistance route exceeded baseline's resistance on identical support"
            )
        comparisons.append(record)
        for label, route in [("baseline", baseline), ("resistance", selected)]:
            for sequence, (u, v, key) in enumerate(route.edges):
                geometry = edges.loc[
                    (edges.u == u) & (edges.v == v) & (edges.key == key), "geometry"
                ].iloc[0]
                route_rows.append(
                    dict(
                        pair=i, route=label, sequence=sequence, u=u, v=v, key=key, geometry=geometry
                    )
                )
    output.mkdir(parents=True, exist_ok=True)
    if overwrite:
        for name in ARTIFACTS:
            (output / name).unlink(missing_ok=True)
    ox.io.save_graphml(graph, output / "walking.graphml")
    ox.io.save_graphml(supported, output / "supported.graphml")
    export_edges = edges.copy()
    for column in export_edges.columns:
        if column != "geometry" and export_edges[column].dtype == "object":
            export_edges[column] = export_edges[column].map(
                lambda value: json.dumps(value) if isinstance(value, (list, tuple, dict)) else value
            )
    export_edges.to_file(output / "edges.gpkg", driver="GPKG", index=False)
    edges.drop(columns="geometry").to_csv(output / "edges.csv", index=False)
    nodes.drop(columns="geometry").to_csv(output / "nodes.csv")
    if route_rows:
        gpd.GeoDataFrame(route_rows, crs=edges.crs).to_crs(4326).to_file(
            output / "routes.geojson",
            driver="GeoJSON",
            index=False,
        )
    (output / "route_comparison.json").write_text(
        json.dumps(comparisons, indent=2, allow_nan=False) + "\n"
    )
    if config.get("map", False):
        from .visualize import save_map

        routes = gpd.GeoDataFrame(route_rows, crs=edges.crs) if route_rows else None
        save_map(edges, output / "map.html", boundary=boundary, routes=routes)
    manifest = {
        "engine": "PathéResistance",
        "version": version("pathe-resistance"),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "inputs": [str(p) for p in source_paths],
        "graph": graph_summary(graph),
        "supported_graph": graph_summary(supported),
        "unsupported_edges": graph.number_of_edges() - supported.number_of_edges(),
        "model": asdict(model),
        "route_pairs": len(comparisons),
        "feature_coverage": {
            name: int(edges[name].notna().sum())
            for name in ["tree_cover", "heat", "traffic"]
            if name in edges
        },
        "packages": {
            name: version(name) for name in ["osmnx", "rasterio", "geopandas", "networkx"]
        },
        "artifacts": [name for name in ARTIFACTS if (output / name).exists()],
        "interpretation": "Scenario resistance in equivalent seconds; not measured walking time, shade, fatigue or safety.",
        "topology": "All mapped components retained. No artificial connections or entrance snapping.",
        "boundary": "Routing buffer reduces truncation effects; finite extent does not certify route completeness.",
        "data_rights": "Code license does not license input data, OSM-derived databases, or model weights.",
    }
    # manifest is written last: its presence marks a successful complete run.
    manifest["artifacts"] = sorted(set(manifest["artifacts"]) | {"manifest.json"})
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    return manifest
