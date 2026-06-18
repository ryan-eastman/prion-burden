"""Phase 0 — recover µm/px from TIFF metadata into a scale table.

Faithful port of ``00_calibrate_scalebars``. Tries, in order: Olympus SIS
(``sis_metadata``, metres), OME-XML ``PhysicalSizeX``, ImageJ unit + resolution,
then plain TIFF cm/inch resolution tags (often print DPI — verify before
trusting). Returns NaN when nothing usable is embedded.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile

from .config import IMG_EXTS
from .discovery import discover_images


def _to_um(val: float, unit: str | None) -> float:
    u = (unit or "").lower()
    if u in ("um", "micron", "microns", "micrometer", "micrometre"):
        return val
    if u in ("nm", "nanometer"):
        return val / 1000.0
    if u in ("mm", "millimeter"):
        return val * 1000.0
    if u in ("m", "meter"):
        return val * 1e6
    return val  # assume microns if unit is absent


def um_per_px_from_metadata(path: Path) -> float:
    """Best-effort µm/px from a single TIFF's embedded calibration."""
    try:
        with tifffile.TiffFile(path) as tf:
            pg = tf.pages[0]
            xres = pg.tags.get("XResolution")
            # 0) Olympus SIS (sis_metadata): pixelsizex is in METERS
            try:
                sis = tf.sis_metadata
                if sis and sis.get("pixelsizex"):
                    return float(sis["pixelsizex"]) * 1e6
            except Exception:
                pass
            # 1) OME-XML PhysicalSizeX
            if tf.is_ome and tf.ome_metadata:
                try:
                    for el in ET.fromstring(tf.ome_metadata).iter():
                        if el.tag.endswith("Pixels") and el.get("PhysicalSizeX"):
                            return _to_um(
                                float(el.get("PhysicalSizeX")),
                                el.get("PhysicalSizeXUnit", "um"),
                            )
                except Exception:
                    pass
            # 2) ImageJ: unit + XResolution (stored as pixels per unit)
            ij = tf.imagej_metadata or {}
            if ij.get("unit") and xres is not None:
                num, den = xres.value
                if num:
                    return _to_um(den / num, ij.get("unit"))
            # 3) plain TIFF resolution in cm/inch (often print DPI — VERIFY)
            unit = pg.tags.get("ResolutionUnit")
            if xres is not None and unit is not None and unit.value in (2, 3):
                num, den = xres.value
                if num:
                    per_unit_um = 1e4 if unit.value == 3 else 25400.0  # cm or inch
                    return per_unit_um / (num / den)
    except Exception:
        pass
    return np.nan


def build_scale_table(
    data_dir: Path,
    out_path: Path,
    exts: set[str] = IMG_EXTS,
) -> pd.DataFrame:
    """Recover µm/px for every image and write ``scale_table.csv``.

    Returns the table; also writes it to ``out_path`` (parent created as needed).
    """
    image_paths = discover_images(data_dir, exts)
    # Pass explicit columns so an image-less directory still yields the schema
    # (an empty DataFrame with no columns would KeyError on `um_per_px`).
    mt = pd.DataFrame(
        [dict(image=p.name, um_per_px=um_per_px_from_metadata(p)) for p in image_paths],
        columns=["image", "um_per_px"],
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mt.to_csv(out_path, index=False)
    return mt
