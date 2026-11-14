# Configuration and feature contracts

Run `pathe-resistance run path/to/config.json`. Paths are relative to that JSON file. Unknown top-level keys are rejected so typos do not silently change your experiment.

## Inputs

- `boundary`: Polygon/MultiPolygon GIS file with a CRS. Multiple features are unioned for downloads. Full study boundaries and routing extent remain distinct.
- `graph`: optional OSMnx GraphML. When supplied, no OSM download or clipping occurs. Its topology, extent and length attributes are caller inputs.
- `buffer_m`: nonnegative download buffer; default 500 m. Used only when extracting a new graph. A suitable local metric CRS is used for buffering.
- `rasters`: zero or more `tree_cover`, `heat`, `traffic` specifications. Each needs `path`; options below.
- `edge_features`: optional CSV keyed by unique `(u,v,key)`. Feature columns must not collide with existing graph/raster columns. Unknown edge IDs are errors; absent feature rows remain unknown.
- `routes`: list of `{"origin": NODE_ID, "destination": NODE_ID}` objects. OSM node IDs are integers. No implicit snapping to roads or building entrances.
- `model`: numeric fields from `ResistanceModel`, described below.
- `output`: output directory. Required. Existing nonempty output requires explicit `--overwrite`.
- `map`: optional boolean; default false. Requires the `map` installation extra.

Start with a small public area. Large downloads can hit Overpass limits; obtain or prepare a local OSMnx GraphML for repeated or regional analysis. This release does not include an automatic PBF parser or imagery acquisition service.

## Raster specification

| Option | Default | Contract |
| --- | --- | --- |
| `path` | required | Georeferenced raster readable by Rasterio |
| `mode` | `fraction` | `binary`, `fraction`, `percent` |
| `band` | 1 | One-based raster band |
| `buffer_m` | 10 | Corridor half-width in meters |
| `min_coverage` | 0.98 | Required valid pixel-center fraction |
| `scale`, `offset` | 1, 0 | Physical value = stored value × scale + offset |
| `max_window_pixels` | 4,000,000 | Per-edge window guard; split extremely long edges when needed |

Buffering occurs in metric coordinates, then corridors transform to the raster CRS. Pixel-center masks are evaluated on the source grid, including expected pixels outside its bounds. Exact reversed corridor geometries reuse samples. NoData, nonfinite, out-of-range and off-raster pixels are not observations. When raster scale/offset metadata is nonidentity, matching values must be explicitly supplied.

For each feature `tree_cover`, outputs include:

- `tree_cover_observed`: mean over valid sampled pixels, even when coverage is incomplete.
- `tree_cover_coverage`: valid / expected corridor pixel centers.
- `tree_cover`: mean only when coverage meets the threshold, otherwise NaN.

Only the supported feature enters the cost. Probability surfaces are allowed but their averages are probability proxies rather than literal canopy percentages. Zero tree cover is a known exposed observation; unknown imagery is not exposed ground.

## Model

`speed_mps=1.2`, `canopy_weight=1`, `canopy_power=1`, `heat_weight=0`, `heat_interaction=0`, `traffic_weight=0`.

The model validates finite nonnegative coefficients, positive speed and positive canopy power. Feature values must lie in [0,1]. Missing features with active weights produce unknown costs. Disabled terms require no feature. Zero-length edges are permitted with zero baseline/cost, while negative or unknown lengths are errors.

The EmPath shade-priority equation is reproduced by `examples/shade_priority.json` and `ResistanceModel.shade_priority()`:

```text
w = (length / 1.2) × [1 + 6 × (1 − tree_cover)^2 × (1 + heat) + traffic]
```

This transfers an explicit scenario equation, not a trained or calibrated model. It deliberately does not reproduce silent block-canopy fallbacks or city-wide midpoint joins. If you want fallbacks, prepare them upstream with a per-edge source field and document the rule. Heat and traffic must already be normalized against declared physical/reference scales.

## Routes and missing support

Cost and time routes are computed on the same graph of supported edges. The full-network time baseline is separately reported. The engine validates every weight before routing; a missing NetworkX weight cannot silently become 1. Parallel edges retain their actual keys. Unreachable pairs have an explicit status. Same-node trips return zero length and time without a route geometry.

Finite extraction boundaries can omit useful detours or outside destinations. Increase the graph buffer and compare outcomes before claiming complete accessibility. This package does not certify those bounds or validate entrances/crossings.
