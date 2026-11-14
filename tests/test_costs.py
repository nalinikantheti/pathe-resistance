import numpy as np
import pandas as pd
import pytest

from pathe_resistance import ResistanceModel, apply_resistance


def test_shade_priority_matches_empath_equation():
    frame = pd.DataFrame({"length": [120.0], "tree_cover": [0.2], "heat": [0.8], "traffic": [0.3]})
    result = apply_resistance(frame, ResistanceModel.shade_priority())
    assert result.resistance_s.iloc[0] == pytest.approx(100 * (1 + 6 * 0.8**2 * 1.8 + 0.3))
    assert result.baseline_s.iloc[0] == 100


def test_missing_required_feature_stays_unknown_but_disabled_feature_is_optional():
    frame = pd.DataFrame({"length": [120, 120, 120], "tree_cover": [0.5, np.nan, 1.1]})
    result = apply_resistance(frame)
    assert result.cost_supported.tolist() == [True, False, False]
    assert result.resistance_s.iloc[1:].isna().all()
    zero = apply_resistance(frame, ResistanceModel(canopy_weight=0))
    assert zero.resistance_s.tolist() == [100, 100, 100]


def test_homogeneous_subdivision_does_not_change_total_cost():
    whole = pd.DataFrame({"length": [120], "tree_cover": [0.3]})
    split = pd.DataFrame({"length": [40, 80], "tree_cover": [0.3, 0.3]})
    assert apply_resistance(whole).resistance_s.sum() == pytest.approx(
        apply_resistance(split).resistance_s.sum()
    )


@pytest.mark.parametrize(
    "options", [{"speed_mps": 0}, {"canopy_weight": -1}, {"heat_weight": np.nan}]
)
def test_reject_invalid_model(options):
    with pytest.raises(ValueError):
        ResistanceModel(**options)


def test_reject_invalid_length():
    with pytest.raises(ValueError, match="length"):
        apply_resistance(pd.DataFrame({"length": [-1], "tree_cover": [1]}))
