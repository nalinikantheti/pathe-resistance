"""Sample georeferenced model output beside paths, preserving unknown coverage."""

from math import isfinite

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import geometry_mask, geometry_window
from shapely.geometry import mapping

from .graph import metric_crs


def sample_corridors(
    edges,
    raster_path,
    *,
    name="tree_cover",
    mode="fraction",
    buffer_m=10,
    min_coverage=0.98,
    band=1,
    scale=1.0,
    offset=0.0,
    max_window_pixels=4_000_000,
):
    """Sample pixel centers in a path buffer; return feature/coverage columns.

    mode is binary (0/1), fraction (0..1), or percent (0..100). Physical scaling
    uses the explicit scale/offset; nonidentity raster metadata requires an exact
    explicit match to prevent accidental double scaling. NoData, invalid values
    and off-raster pixels reduce coverage. Insufficient coverage yields NaN.
    """
    if mode not in {"binary", "fraction", "percent"}:
        raise ValueError("mode must be binary, fraction or percent")
    if not isfinite(buffer_m) or buffer_m <= 0 or not 0 <= min_coverage <= 1:
        raise ValueError("buffer_m must be positive and min_coverage must be in [0,1]")
    if not isfinite(scale) or not isfinite(offset) or scale <= 0:
        raise ValueError("scale must be positive; scale/offset must be finite")
    if edges.empty:
        raise ValueError("Cannot sample an empty edge table")
    if edges.geometry.isna().any() or edges.geometry.is_empty.any():
        raise ValueError("Edges have missing/empty geometry")
    metric = edges.to_crs(metric_crs(edges))
    corridors = gpd.GeoSeries(metric.geometry.buffer(buffer_m), crs=metric.crs)
    observed, coverage = [], []
    cache = {}
    with rasterio.open(raster_path) as src:
        if src.crs is None or band < 1 or band > src.count:
            raise ValueError("Raster needs a CRS and the requested band")
        if src.scales[band - 1] != 1 or src.offsets[band - 1] != 0:
            if not np.allclose([scale, offset], [src.scales[band - 1], src.offsets[band - 1]]):
                raise ValueError("Declare the raster's metadata scale/offset explicitly")
        corridors = corridors.to_crs(src.crs)
        for corridor in corridors:
            key = corridor.normalize().wkb
            if key in cache:
                mean, fraction = cache[key]
            else:
                geom = mapping(corridor)
                window = geometry_window(src, [geom], boundless=True)
                if window.width * window.height > max_window_pixels:
                    raise ValueError(
                        "Corridor window too large; split long edges or raise max_window_pixels"
                    )
                pixels = src.read(band, window=window, masked=True, boundless=True)
                inside = geometry_mask(
                    [geom],
                    out_shape=pixels.shape,
                    transform=src.window_transform(window),
                    invert=True,
                    all_touched=False,
                )
                values = pixels.data.astype(float) * scale + offset
                upper = 100 if mode == "percent" else 1
                valid = inside & ~np.ma.getmaskarray(pixels) & np.isfinite(values)
                valid &= (values >= 0) & (values <= upper)
                if mode == "binary":
                    valid &= (values == 0) | (values == 1)
                expected = int(inside.sum())
                fraction = float(valid.sum() / expected) if expected else 0.0
                mean = float(values[valid].mean() / upper) if valid.any() else np.nan
                cache[key] = (mean, fraction)
            observed.append(mean)
            coverage.append(fraction)
    result = edges.copy()
    result[f"{name}_observed"] = observed
    result[f"{name}_coverage"] = coverage
    result[name] = np.where(np.asarray(coverage) >= min_coverage, observed, np.nan)
    return result
