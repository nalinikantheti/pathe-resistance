"""Nonnegative, additive scenario costs. No trained comfort model is implied."""

from dataclasses import asdict, dataclass
from math import isfinite

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ResistanceModel:
    """Explicit preferences; zero weights disable their corresponding features.

    Cost = length / speed * [1 + wc*(1-C)**p*(1 + interaction*H) + wh*H + wq*Q].
    C, H, Q are tree fraction, normalized heat burden, normalized traffic burden.
    Cost is expressed in equivalent seconds, not predicted elapsed time or fatigue.
    """

    speed_mps: float = 1.2
    canopy_weight: float = 1.0
    heat_weight: float = 0.0
    traffic_weight: float = 0.0
    canopy_power: float = 1.0
    heat_interaction: float = 0.0

    def __post_init__(self):
        for name, value in asdict(self).items():
            if not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f"{name} must be a finite number")
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")
        if self.speed_mps <= 0 or self.canopy_power <= 0:
            raise ValueError("speed_mps and canopy_power must be positive")

    @classmethod
    def shade_priority(cls):
        """The explicit EmPath shade-priority scenario, without implicit fallbacks."""
        return cls(canopy_weight=6, traffic_weight=1, canopy_power=2, heat_interaction=1)


def _fraction(frame, column):
    if column not in frame:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(values.between(0, 1))


def apply_resistance(edges, model=None):
    """Return a copy with baseline_s, resistance_s and cost_supported.

    Required unknown/out-of-range features yield NaN, never zero burden.
    Invalid lengths raise an error rather than producing unusable graph weights.
    """
    model = model or ResistanceModel()
    result = edges.copy()
    length = pd.to_numeric(result["length"], errors="coerce")
    if not (np.isfinite(length) & (length >= 0)).all():
        raise ValueError("Every edge needs a finite, nonnegative length in meters")
    result["baseline_s"] = length / model.speed_mps
    penalty = pd.Series(0.0, index=result.index)
    known = pd.Series(True, index=result.index)
    tree = _fraction(result, "tree_cover")
    heat = _fraction(result, "heat")
    traffic = _fraction(result, "traffic")
    if model.canopy_weight:
        known &= tree.notna()
        canopy = model.canopy_weight * (1 - tree) ** model.canopy_power
        if model.heat_interaction:
            known &= heat.notna()
            canopy *= 1 + model.heat_interaction * heat
        penalty += canopy
    if model.heat_weight:
        known &= heat.notna()
        penalty += model.heat_weight * heat
    if model.traffic_weight:
        known &= traffic.notna()
        penalty += model.traffic_weight * traffic
    result["resistance_s"] = (result.baseline_s * (1 + penalty)).where(known)
    result["cost_supported"] = known
    return result
