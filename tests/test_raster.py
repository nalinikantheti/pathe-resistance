import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import LineString

from pathe_resistance.raster import sample_corridors


def write_raster(path, pixels, nodata=255):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=10,
        height=10,
        count=1,
        dtype="uint8",
        crs=3857,
        transform=from_origin(0, 100, 10, 10),
        nodata=nodata,
    ) as dst:
        dst.write(pixels, 1)


def test_zero_tree_is_valid_and_nodata_is_unknown(tmp_path):
    path = tmp_path / "mask.tif"
    pixels = np.zeros((10, 10), dtype="uint8")
    pixels[:, 5:] = 255
    write_raster(path, pixels)
    edges = gpd.GeoDataFrame(
        geometry=[LineString([(10, 50), (40, 50)]), LineString([(60, 50), (90, 50)])], crs=3857
    )
    result = sample_corridors(edges, path, mode="binary", buffer_m=6)
    assert result.tree_cover.iloc[0] == 0
    assert result.tree_cover_coverage.iloc[0] == 1
    assert np.isnan(result.tree_cover.iloc[1])
    assert result.tree_cover_coverage.iloc[1] == 0


def test_off_raster_area_reduces_coverage(tmp_path):
    path = tmp_path / "mask.tif"
    write_raster(path, np.ones((10, 10), dtype="uint8"))
    edges = gpd.GeoDataFrame(geometry=[LineString([(-50, 50), (50, 50)])], crs=3857)
    result = sample_corridors(edges, path, mode="binary", buffer_m=6)
    assert 0 < result.tree_cover_coverage.iloc[0] < 0.7
    assert np.isnan(result.tree_cover.iloc[0])
    assert result.tree_cover_observed.iloc[0] == 1


def test_percent_is_normalized_once_and_fraction_mode_rejects_percent_values(tmp_path):
    path = tmp_path / "mask.tif"
    write_raster(path, np.full((10, 10), 75, dtype="uint8"))
    edges = gpd.GeoDataFrame(geometry=[LineString([(10, 50), (90, 50)])], crs=3857)
    assert sample_corridors(edges, path, mode="percent", buffer_m=6).tree_cover.iloc[
        0
    ] == pytest.approx(0.75)
    assert np.isnan(sample_corridors(edges, path, mode="fraction", buffer_m=6).tree_cover.iloc[0])


def test_geographic_edges_reproject_without_buffering_in_degrees(tmp_path):
    path = tmp_path / "mask.tif"
    write_raster(path, np.ones((10, 10), dtype="uint8"))
    edges = gpd.GeoDataFrame(geometry=[LineString([(10, 50), (90, 50)])], crs=3857).to_crs(4326)
    assert sample_corridors(edges, path, mode="binary", buffer_m=6).tree_cover.iloc[0] == 1
