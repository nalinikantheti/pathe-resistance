# From a fresh clone to your own application

PathéResistance supplies the graph, environmental-feature and routing backend. A Python software engineer can adapt it to Fremont or another city without changing the core. You will still need local geospatial inputs and an application layer. This guide walks through that boundary explicitly.

## 1. Clone and install

```bash
git clone https://github.com/nalinikantheti/pathe-resistance.git
cd pathe-resistance
python3 -m venv .venv
source .venv/bin/activate
python -m pip install '.[dev,map]'
```

Use Python 3.11 or newer. On Windows, activate with `.venv\Scripts\activate` instead. This installs the engine, test/build tools and optional map dependency. It does not install Torch, download imagery, or select an AI model. The package is installed from the checkout, not from a published PyPI release.

```bash
python -m pytest -q
python -m ruff check .
python -m pip check
python -m build
```

The current suite contains 23 tests. CI runs those tests, lint, packaging and the map demo on Python 3.11–3.13. The suite validates deterministic computational behavior, not real-world pedestrian access or segmentation accuracy.

To run `examples/quickstart.ipynb` in VS Code, also install `'.[notebook]'` and register its kernel from the activated environment:

```bash
python -m pip install '.[notebook]'
python -m ipykernel install --user --name pathe-resistance --display-name "Python (PathéResistance)"
```

Choose **Python (PathéResistance)** in the notebook's kernel picker. This must be the new checkout's Python, rather than an unrelated existing environment. Installing the core package alone does not install notebook/kernel support.

## 2. Understand the offline example

```bash
pathe-resistance demo --output demo --map
```

Open `demo/results/map.html` and `demo/results/route_comparison.json`.

The synthetic graph has six nodes and 12 directed edges. Its ordinary-time route is `1 → 2 → 3`, 200 m. With the demo's stated tree preference, the engine chooses `1 → 4 → 5 → 6 → 3`, 400 m. That longer route has a lower modeled resistance because it follows the synthetic tree-adjacent corridor. It still takes longer in modeled ordinary walking time. This demonstrates the mechanism; no AI inference or real imagery is involved.

The engine does not claim that a 400 m walk takes less time than a 200 m walk. It keeps physical distance, baseline walking seconds and resistance cost as separate fields.

## 3. What is in the repository?

Read the files in this order:

| File or directory | What you learn |
| --- | --- |
| `README.md` | Install, first run, input/output contract and interpretation |
| `examples/quickstart.ipynb` | Small Python walkthrough using the synthetic fixture |
| `examples/area.json` | Configuration for your boundary and predicted tree raster |
| `examples/shade_priority.json` | Example with explicit canopy/heat/traffic preferences |
| `src/pathe_resistance/demo.py` | How the tiny fixture is created |
| `src/pathe_resistance/pipeline.py` | The complete orchestration, from config to exports |
| `src/pathe_resistance/graph.py` | Polygon validation, metric buffer and OSM extraction |
| `src/pathe_resistance/raster.py` | Pixel-center corridor samples and missing-data coverage |
| `src/pathe_resistance/costs.py` | The scenario equation and configurable coefficients |
| `src/pathe_resistance/routing.py` | Validated weights and exact parallel-edge selection |
| `src/pathe_resistance/segmentation.py` | Optional tiled pretrained-model inference |
| `src/pathe_resistance/visualize.py` | Optional HTML inspection map |
| `src/pathe_resistance/cli.py` | `demo`, `run`, and `segment` commands |
| `tests/` | Cost invariants, missing values, raster coverage, graph/routing behavior and pipeline integration |
| `docs/CONFIGURATION.md` | Every configuration field, units and missing-data rules |
| `docs/ARCHITECTURE.md` | Extension points and responsibilities |
| `docs/FROM_EMPATH.md` | Adapting existing EmPath outputs and methodological differences |
| `docs/DATA_AND_MODELS.md` | Distinct code, OSM, imagery and model licensing/provenance |
| `CONTRIBUTING.md` | Local development and pull-request expectations |
| `pyproject.toml` | Dependencies, extras, package metadata and CLI entry point |
| `.github/workflows/tests.yml` | Automated checks in clean Linux environments |
| `LICENSE`, `CHANGELOG.md` | Code license and development history |

## 4. Start with a small real Fremont graph

Do this before downloading imagery or running a model. It verifies the geography/network workflow with **tree preference disabled**. The result is an ordinary walking graph, not a GeoAI-enhanced recommendation.

Run this Python snippet from the repository root after installing the package:

```python
import json
from pathlib import Path
import geopandas as gpd
import osmnx as ox
from shapely.geometry import Point
from pathe_resistance.pipeline import run

data = Path("data")
data.mkdir(exist_ok=True)
lat, lon = ox.geocoder.geocode("Fremont Main Library, Fremont, California, USA")
point = gpd.GeoSeries([Point(lon, lat)], crs=4326)
metric_point = point.to_crs(point.estimate_utm_crs())
boundary = gpd.GeoDataFrame(
    {"name": ["Fremont library neighborhood"]},
    geometry=metric_point.buffer(350), crs=metric_point.crs,
).to_crs(4326)
boundary.to_file(data / "fremont-neighborhood.geojson", driver="GeoJSON")

config = {
    "boundary": "fremont-neighborhood.geojson",
    "buffer_m": 100,
    "model": {"canopy_weight": 0},
    "map": True,
    "output": "../outputs/fremont-baseline"
}
path = data / "fremont-baseline.json"
path.write_text(json.dumps(config, indent=2))
manifest = run(path)
print(manifest["graph"])
```

This requests a small 350 m neighborhood with an additional 100 m routing buffer. It is not a full-city extraction. Nominatim/Overpass need internet and may be slow or rate-limited. Repeated geocoding/extraction uses caches. For repeated pipeline runs, use the saved `walking.graphml` as a `graph` input and choose a fresh output directory or explicit `--overwrite`.

For full Fremont, replace the small polygon with a city boundary obtained from the [City of Fremont GIS/Open Data Hub](https://www.fremont.gov/government/departments/gis), or your own defined study area. A mapped OSM administrative boundary is another input option, but should not be assumed identical to the official municipal boundary. The engine estimates a local metric CRS; nothing in it is tied to Plano or Texas.

## 5. Add your own GeoAI result

You need one of:

- An existing, correctly georeferenced tree classification/cover raster; no ML dependency needed.
- Georeferenced aerial RGB imagery and a compatible model, with prediction produced through `segment` or another tool.

Fremont's GIS sources or California's published NAIP imagery are possible starting points. For example, [California's 2022 NAIP dataset](https://lab.data.ca.gov/dataset/naip-2022-4-band-60cm-california) describes a 60 cm aerial imagery product. It is RGB/NIR imagery, not a ready-made tree mask. Imagery acquisition/clipping is an upstream task; this package does not automate it.

Check imagery acquisition date, resolution, RGB band order and model suitability. Choose a model with terms suitable for your intended use; the EmPath research checkpoint is not automatically a permissive commercial default. Remote checkpoint inference requires an immutable commit SHA and an explicit tree-class index.

Once you have `data/fremont-trees.tif`, create `data/fremont-tree-routing.json`:

```json
{
  "graph": "../outputs/fremont-baseline/walking.graphml",
  "rasters": {
    "tree_cover": {
      "path": "fremont-trees.tif",
      "mode": "binary",
      "buffer_m": 10,
      "min_coverage": 0.98
    }
  },
  "model": {"canopy_weight": 2},
  "output": "../outputs/fremont-tree-routing",
  "map": true
}
```

```bash
pathe-resistance run data/fremont-tree-routing.json
```

The raster must cover your **routing extent**, including its buffer. Otherwise unsupported edges may be excluded from resistance routing. Binary values are 0/1, and the raster's NoData must be declared correctly. A colored PNG screenshot is not a georeferenced prediction raster.

`canopy_weight=2` is an explicit experiment preference, not a fitted Fremont coefficient. Start with tree cover alone; add normalized heat/traffic only when you have suitable data and have documented its scales. Inspect `manifest.json` and per-edge coverage before interpreting routes.

## 6. Select endpoints and request a route

Use the node IDs in `nodes.csv` or edge endpoint IDs in the inspection map. Add actual IDs to the config's `routes` list to export route comparisons. For a Python backend, load a saved graph with its custom weight fields typed explicitly:

```python
from dataclasses import asdict
import osmnx as ox
from pathe_resistance import shortest_route, supported_graph

graph = ox.io.load_graphml(
    "outputs/fremont-tree-routing/supported.graphml",
    edge_dtypes={"baseline_s": float, "resistance_s": float},
)
graph = supported_graph(graph)
# Replace origin_node/destination_node with actual IDs from this graph.
route = shortest_route(graph, origin_node, destination_node)
payload = asdict(route)
```

`payload` contains ordered node IDs, exact `(u,v,key)` edge IDs, distance, modeled walking seconds and resistance cost. To draw it in another frontend, look up the selected edge geometries in the GraphML or `edges.gpkg` and serialize them to GeoJSON. Batch configuration runs already export those geometries as `routes.geojson`.

Do not substitute nearest-node snapping for entrance validation without explaining the approximation. An address may be nearest to an inaccessible road or a path separated by a fence. Handle missing nodes and unreachable paths in the application.

## 7. Build a user-facing application

A practical design is:

```text
Offline job: boundary + graph + prediction raster → weighted graph + metadata
Web service: load graph once → validate requested endpoints/profile → return route + geometry
Frontend: map + start/end selection + preference controls + distance/time/coverage explanation
```

For example, a FastAPI service and a Leaflet/MapLibre frontend can use the Python API and exported data. Those are integration choices, not included servers or apps. The package does not currently provide an address geocoder, live GPS navigation, hosted API, place search, automatic POI catalog, imagery downloader or scalable multi-user serving infrastructure.

Keep graph/raster preparation out of HTTP requests. Precompute a few well-described preference profiles, or explicitly recompute/cache weights when a profile changes. Test latency and memory on your actual area and expected traffic. Current routing validates weights on each call; this is a correctness-oriented prototype, not a high-throughput routing server.

Show distance and modeled ordinary walking time separately from resistance. Describe the environmental signal as predicted tree adjacency, not guaranteed current shade. Validate local paths/crossings and model predictions before presenting results as dependable public guidance. For production basemaps/geocoding, select services that meet your usage needs and preserve required attribution.

## What the successful quickstart proves

It proves that the package installs, computes inspectable features/costs, preserves unknowns, and routes on a well-defined graph. The automated suite does not prove real imagery/model compatibility, Fremont segmentation accuracy, safe legal crossings, full-city route completeness or application scalability. Those require project-specific tests and validation.
