import pytest

from pathe_resistance.segmentation import segment_rgb


def test_remote_model_requires_pinned_revision_before_any_download(tmp_path):
    with pytest.raises(ValueError, match="pinned"):
        segment_rgb(
            tmp_path / "rgb.tif", tmp_path / "trees.tif", model="example/model", tree_class=1
        )


def test_never_overwrites_source(tmp_path):
    with pytest.raises(FileExistsError):
        segment_rgb(tmp_path / "rgb.tif", tmp_path / "rgb.tif", model="example/model", tree_class=1)
