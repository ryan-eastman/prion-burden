"""Synthetic demo cohort — lets a new user verify their install with no data.

``make_synthetic_cohort`` writes a handful of small, labelled TIFFs (with an
embedded scale and a matching animal key) that look enough like the real DAB/IHC
images for the whole pipeline to run on them. ``prion demo`` builds this cohort
and runs calibrate + Phase 1 end-to-end. The same generator backs the test
suite, so the demo is exercised on every CI run.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import tifffile
from skimage import color

# HED stain amounts: faint counterstain (grey tissue) + moderate DAB (brown).
# Chosen so blobs read as positive *tissue*, not as dark annotation.
_HEMA = 0.05
_DAB = 0.30

# Default deposits for a single demo/test image: (row, col, radius), well apart.
DEFAULT_BLOBS = [(30, 40, 8), (30, 110, 8), (85, 70, 8)]

# (filename, species, condition, animal, n_blobs) — treatment carries more
# deposits than control, so the demo reproduces the expected biology
# (control low burden, treatment clearly elevated).
_SPECS = [
    ("GtDeer_treatment_cerebellum_4x_01.tif", "deer", "treatment", "D1", 5),
    ("GtDeer_treatment_cerebellum_4x_02.tif", "deer", "treatment", "D2", 4),
    ("GtElk_treatment_cerebellum_4x_01.tif", "elk", "treatment", "E1", 4),
    ("GtElk_treatment_cerebellum_4x_02.tif", "elk", "treatment", "E2", 3),
    ("WT_control_cerebellum_4x_01.tif", "wt", "control", "C1", 1),
    ("WT_control_cerebellum_4x_02.tif", "wt", "control", "C2", 1),
]


def make_dab_image(blobs=DEFAULT_BLOBS, h: int = 120, w: int = 160) -> np.ndarray:
    """RGB uint8 image: light tissue everywhere + DAB blobs as ``(cy, cx, r)``."""
    hed = np.zeros((h, w, 3), float)
    hed[..., 0] = _HEMA
    yy, xx = np.ogrid[:h, :w]
    for cy, cx, r in blobs:
        hed[(yy - cy) ** 2 + (xx - cx) ** 2 <= r**2, 2] = _DAB
    rgb = np.clip(color.hed2rgb(hed), 0, 1)
    return (rgb * 255).astype(np.uint8)


def make_synthetic_cohort(root: str | Path) -> tuple[Path, Path]:
    """Write a 6-image labelled cohort under ``root``.

    Creates ``root/images/*.tif`` (each with a ~5 µm/px scale embedded in the
    TIFF resolution tags) and ``root/animal_key.csv``. Returns
    ``(images_dir, animal_key_path)``.
    """
    root = Path(root)
    data = root / "images"
    data.mkdir(parents=True, exist_ok=True)

    rows = ["image,animal,species,condition,region"]
    for i, (fname, species, condition, animal, n) in enumerate(_SPECS):
        centers = [
            (25 + 18 * (j % 6), 25 + 22 * (j // 6), 7 + (i % 3)) for j in range(n)
        ]
        img = make_dab_image(blobs=centers)
        # resolutionunit=CENTIMETER, 2000 px/cm -> 1e4/2000 = 5.0 µm/px
        tifffile.imwrite(
            data / fname, img, resolution=(2000, 2000), resolutionunit="CENTIMETER"
        )
        rows.append(f"{fname},{animal},{species},{condition},cerebellum")

    key = root / "animal_key.csv"
    key.write_text("\n".join(rows) + "\n")
    return data, key
