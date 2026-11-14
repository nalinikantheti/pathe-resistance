# PathéResistance

**Turn a walking graph and GeoAI rasters into an inspectable, environmentally weighted routing network.**

PathéResistance is the reusable engine that was used to create [EmPath](https://github.com/nalinikantheti/EmPath). Bring a boundary, an OpenStreetMap graph, and your own georeferenced tree predictions. Get edge features, explicit resistance costs, and comparable routes back. Replace the city, imagery, model or weights without editing the package.

```text
Boundary / GraphML → walking graph → GeoAI raster samples → resistance costs → routes
                                         ↑
                      your predicted raster, or optional RGB segmentation
```

This is an early research toolkit. Tree adjacency is a canopy proxy, not measured shade. Resistance is an explicit scenario, not a prediction of fatigue, safety or actual travel time.

**New to the project?** Follow the [developer walkthrough](docs/DEVELOPER_WALKTHROUGH.md): clone → test → offline demo → a small Fremont graph → your own GeoAI inputs → a user-facing application. It explains what the engine provides and what you still need to build.

## Try it in five minutes

Python 3.11+ is required. From this repository:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install .
pathe-resistance demo --output demo
```

The demo runs **without API calls or model downloads**. It creates six synthetic nodes, a tiny synthetic tree raster, and two alternative routes. It is clearly labeled synthetic; it is not an AI result or a real neighborhood. Read `demo/results/route_comparison.json`: the shorter exposed path differs from the longer route favored by the configured tree preference.

For a visual inspection:

```bash
python -m pip install '.[map]'
pathe-resistance demo --output demo-with-map --map
```

Open `demo-with-map/results/map.html`. Viewing its basemap/JavaScript needs internet. Use a fresh demo directory for each run.

## Use your own area

Copy [examples/area.json](examples/area.json), update its paths, then run:

```bash
pathe-resistance run examples/area.json
```

Every relative path resolves beside the configuration file, not the terminal's current directory. A minimal configuration is:

```json
{
  "boundary": "data/your_boundary.geojson",
  "buffer_m": 500,
  "rasters": {
    "tree_cover": {
      "path": "data/your_tree_predictions.tif",
      "mode": "binary",
      "buffer_m": 10,
      "min_coverage": 0.98
    }
  },
  "model": {"speed_mps": 1.2, "canopy_weight": 1.0},
  "output": "outputs/your_area"
}
```

With `boundary` and no `graph`, the engine requests an OSMnx walking graph. This needs internet and the public Overpass service may be slow or rate-limited. The routing buffer is measured in meters. All mapped components remain present; the engine never invents connections.

To reuse a graph, add `"graph": "data/walking.graphml"`. The engine then makes no network request. Supplied GraphML defines the routing extent; `boundary` is optional and is used for the map, not to silently crop your graph. Input graphs must follow [OSMnx's graph schema](https://osmnx.readthedocs.io/en/stable/getting-started.html): directed parallel edges, node coordinates/CRS, and `length` in meters.

Add routes using graph node IDs:

```json
"routes": [{"origin": 123456789, "destination": 987654321}]
```

If features are missing, edges remain in `walking.graphml` with unknown resistance; `supported.graphml` omits them. Each ordinary-time versus resistance comparison uses the **same supported graph**. A separate full-network baseline exposes changes caused by missing feature coverage. Unreachable trips are reported explicitly.

## Bring your own GeoAI

The core engine consumes a **georeferenced raster**, regardless of how it was produced:

| Mode | Valid pixel values | Meaning |
| --- | --- | --- |
| `binary` | 0 or 1 | Predicted class mask; 1 means tree |
| `fraction` | 0–1 | Tree fraction or model class probability; these are different interpretations |
| `percent` | 0–100 | Canopy percentage; normalized once to 0–1 |

Always declare the raster's real NoData value in its metadata. Unknown pixels and off-raster areas reduce corridor coverage. Values outside the configured range are unknown. Zero canopy is valid. No automatic resampling or missing-as-zero substitution occurs. Probability averages are confidence proxies, not measured canopy fractions.

Optional inference is separate:

```bash
python -m pip install '.[geoai]'
pathe-resistance segment data/rgb.tif outputs/predicted_trees.tif \
  --model YOUR_MODEL_ID --revision YOUR_40_CHARACTER_COMMIT_SHA --tree-class 1
```

Choose a compatible Transformers semantic-segmentation checkpoint, its correct tree-class index, and an immutable revision. Local checkpoint directories are also accepted. RGB imagery must be georeferenced uint8 in bands 1–3. Inference uses tiled context windows, preserves source grid/NoData, and writes a provenance sidecar. No model weights are bundled or downloaded during installation. Real-model inference is optional and is not part of the offline demo.

Review [data and model rights](docs/DATA_AND_MODELS.md) before choosing a checkpoint. The Restor checkpoint used in the EmPath research has separate research-use terms; the MIT license here does not relicense it.

## Understand or change the cost

The configurable equation is:

```text
baseline_s   = length_m / speed_mps
resistance_s = baseline_s × [1 + wc × (1 − C)^p × (1 + interaction × H) + wh × H + wq × Q]
```

`C` is tree cover/proxy, `H` is normalized heat burden, and `Q` is normalized traffic burden, all 0–1. Default: `wc=1`, `p=1`, and the other terms disabled. Coefficients are **declared preferences**, not learned comfort estimates. Resistance seconds are equivalent-cost units; `baseline_s` is shown separately as modeled walking time.

Enable heat/traffic with raster features named `heat` and `traffic`, or join a CSV through `edge_features` with unique `u,v,key` and normalized columns. Choose and document normalization reference ranges yourself; raw temperatures or vehicle counts are not valid 0–1 burdens. Inputs with active weights must be known. See [configuration](docs/CONFIGURATION.md) for the EmPath shade-priority scenario and extension examples.

## Python API

```python
from pathe_resistance import ResistanceModel, apply_resistance
from pathe_resistance.raster import sample_corridors

# edges: a GeoDataFrame with geometry, CRS and length in meters
enriched = sample_corridors(edges, "trees.tif", mode="binary", buffer_m=10)
weighted = apply_resistance(enriched, ResistanceModel(canopy_weight=2))
```

For graph routing use `supported_graph` and `shortest_route`, which retain the exact `(u,v,key)` identities of parallel edges. See [architecture](docs/ARCHITECTURE.md) for module responsibilities and the [EmPath migration guide](docs/FROM_EMPATH.md) for existing outputs.

## Outputs

| Artifact | Purpose |
| --- | --- |
| `walking.graphml` | Full graph with baseline and resistance attributes |
| `supported.graphml` | Graph retaining only finite supported resistance edges |
| `edges.gpkg`, `edges.csv`, `nodes.csv` | GIS and analysis tables, including feature coverage |
| `routes.geojson` | Ordered comparison-route edge geometries, when reachable routes exist |
| `route_comparison.json` | Same-support route comparison and full-network baseline |
| `manifest.json` | Configuration, versions, input references, topology counts and interpretation |
| `map.html` | Optional inspection map when `"map": true` |

Existing nonempty output directories are protected. Use `pathe-resistance run CONFIG --overwrite` to replace only named artifacts. Raw data, models, generated maps and local caches are ignored by Git.

## Develop

```bash
python -m pip install -e '.[dev,map]'
ruff check .
pytest -q
python -m build
```

Tests exercise missing-data coverage, physical units, cost invariance, directed parallel edges, routing comparisons and the entire offline demo. CI targets Python 3.11–3.13. Tests do not call OSM or download model weights. See [CONTRIBUTING.md](CONTRIBUTING.md).

If a mixed Conda/pip environment reports a PROJ database mismatch, use a clean virtual environment or remove inherited `PROJ_DATA`, `PROJ_LIB` and `GDAL_DATA` for that command. On macOS, if an editable install is not importable because its `.pth` file has a hidden file flag, use a regular `python -m pip install .` instead.

**License:** MIT for this repository's code. OSM-derived data, imagery and model checkpoints retain their own licenses and attribution requirements. Read [DATA_AND_MODELS.md](docs/DATA_AND_MODELS.md).
