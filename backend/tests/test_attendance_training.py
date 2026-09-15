import numpy as np
import pandas as pd

from app.attendance.data import FEATURES
from app.attendance.training import metrics


def test_metrics_are_exact_for_perfect_prediction():
    result = metrics(np.array([10.0, 20.0]), np.array([10.0, 20.0]))
    assert result["wape"] == 0
    assert result["rmsle"] == 0
    assert result["within_factor_2"] == 1


def test_feature_names_are_safe_and_unique():
    assert len(FEATURES) == len(set(FEATURES))
    assert all(name.replace("_", "").isalnum() for name in FEATURES)
