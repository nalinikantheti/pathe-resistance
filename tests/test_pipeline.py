import json
import socket

import geopandas as gpd
import numpy as np
import pytest
import rasterio

from pathe_resistance.cli import main
from pathe_resistance.demo import create_demo
from pathe_resistance.pipeline import run


def test_offline_pipeline_changes_route_and_exports_reusable_outputs(tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("Offline demo must not access the network")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    path = create_demo(tmp_path / "demo")
    manifest = run(path)
    assert manifest["graph"]["nodes"] == 6
    assert manifest["unsupported_edges"] == 0
    result = path.parent / "results"
    pairs = json.loads((result / "route_comparison.json").read_text())
    pair = pairs[0]
    assert pair["baseline"]["nodes"] == [1, 2, 3]
    assert pair["resistance"]["nodes"] == [1, 4, 5, 6, 3]
    assert pair["resistance"]["distance_m"] > pair["baseline"]["distance_m"]
    assert pair["resistance"]["objective_cost"] < pair["baseline_resistance_s"]
    assert len(gpd.read_file(result / "routes.geojson")) == 6
    with pytest.raises(FileExistsError):
        run(path)
    run(path, overwrite=True)


def test_unknown_config_key_fails_clearly(tmp_path):
    config = create_demo(tmp_path / "demo")
    value = json.loads(config.read_text())
    value["canpoy_weight"] = 1
    config.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="Unknown configuration"):
        run(config)


def test_cli_error_is_actionable(tmp_path, capsys):
    assert main(["run", str(tmp_path / "missing.json")]) == 2
    assert "Error:" in capsys.readouterr().err


def test_unknown_raster_does_not_invent_routes_or_leave_stale_geometry(tmp_path):
    config = create_demo(tmp_path / "demo")
    run(config)
    raster = config.parent / "trees.tif"
    with rasterio.open(raster, "r+") as dataset:
        dataset.write(np.full((dataset.height, dataset.width), 255, dtype="uint8"), 1)
    manifest = run(config, overwrite=True)
    output = config.parent / "results"
    result = json.loads((output / "route_comparison.json").read_text())[0]
    assert manifest["supported_graph"]["directed_edges"] == 0
    assert manifest["unsupported_edges"] == 12
    assert result["status"] == "unreachable_on_supported_graph"
    assert result["full_network_baseline"]["distance_m"] == 200
    assert not (output / "routes.geojson").exists()
