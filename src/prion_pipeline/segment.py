"""Phase 1 — DAB segmentation and per-object morphometry.

Faithful port of the segmentation/feature cells of
``01_phase1_burden_morphometry``. CPU only; no training, no GPU.

A fixed DAB optical-density cutoff (not a per-image Otsu) is used so that PrP
burden is comparable across images and groups.
"""

from __future__ import annotations

import inspect
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage as ndi
from skimage import color, filters, io, measure, morphology, segmentation, util
from skimage.feature import peak_local_max
from skimage.transform import rescale

from .config import Config
from .discovery import get_um_per_px, parse_metadata

# --- scikit-image compatibility -------------------------------------------
# 0.26 renamed ``min_size``/``area_threshold`` to keyword-only ``max_size``
# ("remove objects/holes whose area is <= size"). Older releases only accept the
# legacy names. Detect once so the pipeline runs across installed versions.
_RSO_HAS_MAX = "max_size" in inspect.signature(morphology.remove_small_objects).parameters
_RSH_HAS_MAX = "max_size" in inspect.signature(morphology.remove_small_holes).parameters


def _remove_small_objects(labels: np.ndarray, size: int) -> np.ndarray:
    with warnings.catch_warnings():
        # We intentionally pass a label image; silence skimage's "only one
        # label" guess-warning that fires when an image has a single object.
        warnings.filterwarnings("ignore", message="Only one label was provided")
        if _RSO_HAS_MAX:
            return morphology.remove_small_objects(labels, max_size=size)
        return morphology.remove_small_objects(labels, min_size=size)


def _remove_small_holes(mask: np.ndarray, size: int) -> np.ndarray:
    if _RSH_HAS_MAX:
        return morphology.remove_small_holes(mask, max_size=size)
    return morphology.remove_small_holes(mask, area_threshold=size)


# --- image loading ---------------------------------------------------------
def load_and_standardize(
    path: Path,
    cfg: Config,
    scale: dict[str, float],
) -> tuple[np.ndarray, float]:
    """Load an RGB image; resample only for MIXED-magnification cohorts.

    Returns ``(img, effective_um_per_px)``. When ``target_um_per_px`` is unset
    (the single-magnification default) the native image and scale are returned.
    """
    img = io.imread(path)
    if img.ndim == 2:
        img = color.gray2rgb(img)
    img = img[..., :3]
    upp = get_um_per_px(path, scale)
    target = cfg.target_um_per_px
    if target is None or np.isnan(upp):
        return img, upp
    factor = upp / target
    if abs(factor - 1) > 1e-3:
        img = rescale(
            img, factor, channel_axis=-1, anti_aliasing=True, preserve_range=True
        ).astype(np.uint8)
    return img, float(target)


# --- DAB / tissue ----------------------------------------------------------
def dab_channel(img_rgb: np.ndarray) -> np.ndarray:
    """DAB (brown) optical-density channel via colour deconvolution."""
    return color.rgb2hed(util.img_as_float(img_rgb))[..., 2]


def tissue_mask(img_rgb: np.ndarray) -> np.ndarray:
    """Tissue = not-white background AND not-black annotations (scale bar/text)."""
    g = color.rgb2gray(util.img_as_float(img_rgb))
    return (g < 0.92) & (g > 0.05)


def segment_dab(
    img_rgb: np.ndarray,
    eff_upp: float,
    cfg: Config,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, float]:
    """Threshold the DAB channel, watershed-split, size-filter.

    Returns ``(labels, positive_mask, tissue_mask, area_fraction, threshold)``.
    """
    dab = dab_channel(img_rgb)
    tis = tissue_mask(img_rgb)
    blank = np.zeros(dab.shape, int)
    if tis.sum() == 0:
        return blank, blank.astype(bool), tis, 0.0, np.nan
    t = (
        filters.threshold_otsu(dab[tis])
        if cfg.dab_threshold is None
        else cfg.dab_threshold
    )
    pos = (dab > t) & tis
    pos = _remove_small_holes(pos, 64)
    area_frac = pos.sum() / tis.sum()
    if pos.sum() == 0:
        return blank, pos, tis, area_frac, t
    dist = ndi.distance_transform_edt(pos)
    peaks = peak_local_max(dist, min_distance=cfg.min_peak_dist, labels=pos)
    markers = np.zeros(dist.shape, int)
    for i, (r, c) in enumerate(peaks, start=1):
        markers[r, c] = i
    labels = segmentation.watershed(-dist, markers, mask=pos)
    if not np.isnan(eff_upp):
        min_px = int(max(cfg.min_object_um2 / (eff_upp**2), 1))
        labels = _remove_small_objects(labels, min_px)
    return labels, pos, tis, area_frac, t


# --- features --------------------------------------------------------------
def object_features(labels: np.ndarray, eff_upp: float) -> pd.DataFrame:
    """Per-object morphometry table (empty frame if no objects)."""
    if labels.max() == 0:
        return pd.DataFrame()
    props = measure.regionprops_table(
        labels,
        properties=[
            "label", "area", "perimeter", "eccentricity", "solidity", "extent",
            "axis_major_length", "axis_minor_length", "centroid",
        ],
    )
    df = pd.DataFrame(props)
    upp = eff_upp if not np.isnan(eff_upp) else 1.0
    df["area_um2"] = df["area"] * upp**2
    df["perimeter_um"] = df["perimeter"] * upp
    df["circularity"] = 4 * np.pi * df["area"] / (df["perimeter"] ** 2 + 1e-9)
    df["aspect_ratio"] = df["axis_major_length"] / (df["axis_minor_length"] + 1e-9)
    return df


def process_image(
    path: Path,
    cfg: Config,
    scale: dict[str, float],
    animal_lookup: dict[str, str],
) -> tuple[dict, pd.DataFrame]:
    """Run the full Phase-1 measurement on one image.

    Returns ``(per_image_summary_row, per_object_features_frame)``.
    """
    meta = parse_metadata(path, cfg, animal_lookup)
    img, upp = load_and_standardize(path, cfg, scale)
    labels, pos, tis, area_frac, t = segment_dab(img, upp, cfg)
    odf = object_features(labels, upp)
    if len(odf):
        odf.insert(0, "image", path.name)
        for k, v in meta.items():
            odf[k] = v
    if not np.isnan(upp):
        tissue_mm2 = tis.sum() * (upp**2) / 1e6
        density = len(odf) / tissue_mm2 if tissue_mm2 > 0 else np.nan
    else:
        tissue_mm2, density = np.nan, np.nan
    summary = dict(
        image=path.name,
        **meta,
        um_per_px=upp,
        pct_area_burden=100 * area_frac,
        n_objects=len(odf),
        tissue_mm2=tissue_mm2,
        density_per_mm2=density,
        mean_area_um2=odf["area_um2"].mean() if len(odf) else np.nan,
        median_circularity=odf["circularity"].median() if len(odf) else np.nan,
        dab_threshold=t,
    )
    return summary, odf
