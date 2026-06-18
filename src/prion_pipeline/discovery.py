"""Image discovery, metadata parsing, and lookup tables.

Ported verbatim (behaviour-wise) from the notebooks' CONFIG and helper cells,
with the hard-coded ``_ANIMAL_KEY = {}`` replaced by an optional CSV so the
animal-grouped statistics actually run.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import Config, IMG_EXTS


def discover_images(data_dir: Path, exts: set[str] = IMG_EXTS) -> list[Path]:
    """Recursively find images, de-duplicated by filename.

    The cohort contains byte-identical copies (e.g. ``controls/GtElk`` mirrors
    ``GtElk/``); keeping the first occurrence of each filename avoids counting an
    image twice. Order is deterministic (sorted by full path).
    """
    seen: set[str] = set()
    paths: list[Path] = []
    for p in sorted(data_dir.rglob("*")):
        if p.suffix.lower() in exts and p.name not in seen:
            seen.add(p.name)
            paths.append(p)
    return paths


def load_scale_table(scale_table: Path) -> dict[str, float]:
    """Map ``image filename -> µm/px`` from Phase-0 output. Empty if missing."""
    try:
        return (
            pd.read_csv(scale_table)
            .set_index("image")["um_per_px"]
            .to_dict()
        )
    except (FileNotFoundError, OSError, KeyError, pd.errors.EmptyDataError):
        return {}


def load_animal_key(animal_key: Path | None) -> dict[str, str]:
    """Map ``image stem -> animal id`` from a CSV with ``image``/``animal`` cols.

    The trailing number in a filename is a per-region IMAGE index, NOT an animal,
    so a real key is required for leakage-free, animal-as-unit statistics. The
    CSV's ``image`` column may carry the file extension or not; both are indexed
    so lookups by ``path.stem`` succeed either way.
    """
    if animal_key is None:
        return {}
    df = pd.read_csv(animal_key)
    if "image" not in df.columns or "animal" not in df.columns:
        raise ValueError(
            f"{animal_key} must have 'image' and 'animal' columns; "
            f"found {list(df.columns)}"
        )
    mapping: dict[str, str] = {}
    for image, animal in zip(df["image"].astype(str), df["animal"].astype(str)):
        mapping[image] = animal
        mapping[Path(image).stem] = animal  # also key by stem
    return mapping


def parse_metadata(path: Path, cfg: Config, animal_lookup: dict[str, str]) -> dict:
    """Derive species/condition/region/magnification/animal from a filename."""
    name = path.stem
    low = name.lower()
    if low.startswith("gtdeer"):
        species = "deer"
    elif low.startswith("gtelk"):
        species = "elk"
    elif low.startswith("wt"):
        species = "wt"
    else:
        species = "unknown"
    condition = (
        "control" if "control" in low
        else ("treatment" if "treatment" in low else "unknown")
    )
    region = next((r for r in cfg.regions if r in low), "unknown")
    mag = next((m for m in cfg.mags if m in low), None)
    image_id = low.split("_")[-1]
    animal = animal_lookup.get(name, animal_lookup.get(path.name, "UNKNOWN"))
    return dict(
        species=species,
        condition=condition,
        region=region,
        magnification=mag,
        image_id=image_id,
        animal=animal,
    )


def get_um_per_px(path: Path, scale: dict[str, float]) -> float:
    """Per-image µm/px from the scale table, or NaN if absent."""
    return scale.get(path.name, np.nan)
