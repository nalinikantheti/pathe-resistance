# Reusing existing EmPath outputs

PathéResistance is extracted from the walking-network, GeoAI and resistance-cost concepts in EmPath. It does not import the EmPath scripts at runtime or require its caches, local virtual environments, Plano service endpoints or generated website.

| EmPath research stage | Portable equivalent |
| --- | --- |
| `build_scope_walking_graph.py`, city graph builders | `graph.extract_walking_graph` or input GraphML |
| `imagery_geoai_demo.py`, `geoai_native_worker.py` | Optional model-selectable `segment_rgb` |
| `summarize_*_geoai.py`, corridor tree sampling | `raster.sample_corridors` |
| `build_step3_friction.py`, `build_shade_priority_costs.py` | `ResistanceModel`, `apply_resistance` |
| Script-specific route reconstruction | `supported_graph`, `shortest_route` |
| Notebook-dependent output paths | Relative JSON configuration and a single pipeline |

## Start with existing files

1. Use an existing OSMnx `walking_graph.graphml` or `walking_network_all_components.graphml` as `graph`.
2. Use the actual predicted 0/1 tree GeoTIFF as a `tree_cover` raster with `mode: binary`. The source NoData must be 255 (or another correctly declared value). A PNG map is not a valid raster substitute.
3. If needed, export normalized heat/traffic as a CSV with `u,v,key,heat,traffic`. Use a many-to-one block join upstream if that is your chosen context model and record that decision; block means are not direct edge measurements.
4. Set the scenario parameters explicitly. `examples/shade_priority.json` matches the EmPath shade-priority equation, but does not inject block-canopy fallbacks.
5. Write to a new output folder and inspect coverage and route support.

The raster sampler uses buffered pixel-center means. The production EmPath shade-priority script uses cross-section point sampling, so individual tree fractions and resulting paths may differ even with identical input imagery. This release preserves the method's intent and equation; it is not a byte-for-byte reproduction of EmPath's published rankings. EmPath uses additional city/block/destination logic that is not part of the portable core.

The entire EmPath codebase, historical notebooks and deployed website remain untouched by this extraction. Before switching EmPath production to this library, compare outputs on a fixed fixture and review methodological differences.
