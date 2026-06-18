"""Shared fixtures, backed by the package's own synthetic-data generator.

Using ``prion_pipeline.demo`` here means the same images that ``prion demo``
ships are exercised by the test suite on every CI run.
"""

from __future__ import annotations

import numpy as np
import pytest

from prion_pipeline.demo import make_dab_image, make_synthetic_cohort


@pytest.fixture
def dab_image() -> np.ndarray:
    return make_dab_image()


@pytest.fixture
def cohort_dir(tmp_path):
    """A small labelled cohort (6 images) with embedded scale + animal key."""
    return make_synthetic_cohort(tmp_path / "cohort")
