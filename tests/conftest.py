"""Shared fixtures: synthetic DAB images and a small synthetic cohort.

No real data is needed — images are generated in HED stain space (via
``skimage.color.hed2rgb``) so the DAB channel responds predictably, and written
as TIFFs with resolution tags so Phase 0 can recover a scale. Blobs use light
haematoxylin (grey tissue) plus a moderate DAB amount so they read as brown
*tissue* rather than dark annotation.
"""

from __future__ import annotations

import numpy as np
import pytest
import tifffile
from skimage import color

HEMA = 0.05  # faint tissue counterstain
DAB = 0.30   # moderate DAB -> brown, stays inside the tissue mask
DEFAULT_BLOBS = [(30, 40, 8), (30, 110, 8), (85, 70, 8)]


def make_dab_image(blobs=DEFAULT_BLOBS, h: int = 120, w: int = 160) -> np.ndarray:
    """RGB uint8: light tissue everywhere + DAB blobs given as (cy, cx, r)."""
    hed = np.zeros((h, w, 3), float)
    hed[..., 0] = HEMA
    yy, xx = np.ogrid[:h, :w]
    for cy, cx, r in blobs:
        hed[(yy - cy) ** 2 + (xx - cx) ** 2 <= r**2, 2] = DAB
    rgb = np.clip(color.hed2rgb(hed), 0, 1)
    return (rgb * 255).astype(np.uint8)


@pytest.fixture
def dab_image() -> np.ndarray:
    return make_dab_image()


@pytest.fixture
def cohort_dir(tmp_path):
    """A small labelled cohort with embedded scale and varied per-image burden.

    Treatment images carry more/larger deposits than controls, and blob radius
    varies per image, so group statistics are well-posed (non-degenerate).
    """
    data = tmp_path / "images"
    data.mkdir()
    # (filename, species, condition, animal, n_blobs)
    specs = [
        ("GtDeer_treatment_cerebellum_4x_01.tif", "deer", "treatment", "D1", 5),
        ("GtDeer_treatment_cerebellum_4x_02.tif", "deer", "treatment", "D2", 4),
        ("GtElk_treatment_cerebellum_4x_01.tif", "elk", "treatment", "E1", 4),
        ("GtElk_treatment_cerebellum_4x_02.tif", "elk", "treatment", "E2", 3),
        ("WT_control_cerebellum_4x_01.tif", "wt", "control", "C1", 1),
        ("WT_control_cerebellum_4x_02.tif", "wt", "control", "C2", 1),
    ]
    rng = np.random.default_rng(0)
    rows = ["image,animal,species,condition,region"]
    for i, (fname, species, condition, animal, n) in enumerate(specs):
        centers = [(25 + 18 * (j % 6), 25 + 22 * (j // 6), 7 + (i % 3)) for j in range(n)]
        img = make_dab_image(blobs=centers)
        tifffile.imwrite(
            data / fname, img, resolution=(2000, 2000), resolutionunit="CENTIMETER"
        )  # 2000 px/cm -> 1e4/2000 = 5.0 µm/px
        rows.append(f"{fname},{animal},{species},{condition},cerebellum")
    key = tmp_path / "animal_key.csv"
    key.write_text("\n".join(rows) + "\n")
    return data, key
