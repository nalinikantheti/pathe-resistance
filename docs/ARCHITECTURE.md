# Architecture

The library has no required web frontend, cloud account, project-specific filesystem layout or global city selection. Importing it starts no work and downloads nothing.

| Module | Responsibility |
| --- | --- |
| `graph.py` | Boundary validation, metric buffering, OSMnx walking extraction and topology summary |
| `segmentation.py` | Optional explicit model inference on supplied RGB imagery |
| `raster.py` | Model-independent corridor sampling and coverage accounting |
| `costs.py` | Validated preferences and additive scenario cost |
| `routing.py` | Supported graph and exact directed edge route identities |
| `pipeline.py` | File/config orchestration, exports and manifest |
| `visualize.py` | Optional HTML inspection map |
| `demo.py` | Synthetic offline end-to-end example |
| `cli.py` | Small command-line interface |

## Extension points

**Different city:** change boundary/graph paths in JSON. No source edits.

**Different model:** supply your own correctly georeferenced raster. The optional inference adapter supports compatible Transformers semantic-segmentation checkpoints, but the core has no model dependency.

**Different features:** sample a normalized raster or join a CSV with `(u,v,key)`. For new factor types beyond tree cover, heat and traffic, add a cost function that returns finite nonnegative per-edge costs and test missing-data behavior. The pipeline's config intentionally accepts only its documented features.

**Different routing objective:** attach the cost attribute to a NetworkX MultiDiGraph, create its `supported_graph`, and call `shortest_route(..., weight="your_cost")`. Also retain `length` and `baseline_s` for comparison. Do not use node-only paths to reconstruct parallel-edge choices.

**Production UI:** consume GraphML/GIS/JSON outputs rather than importing frontend generators into the engine. This repository is an analysis library, not a public geocoding or live-navigation service.

## Reproducibility

The pipeline records exact runtime package versions, configuration and source references. Preserve source rasters and their imagery/model provenance separately. Optional inference pins remote checkpoint revisions; local checkpoint directories are caller-managed. Model source resolution and study-area accuracy must be assessed independently.

No model-training, independent accuracy validation, boundary-completeness certification, demographic scoring, GPS navigation, Census acquisition, live weather service or production imagery downloader is included in 0.1.0. EmPath's complete research application remains in its own repository.
