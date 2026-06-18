"""Batch orchestration for Phase 0 (calibrate) and Phase 1.

Wraps the per-image functions in a cohort loop with progress reporting and CSV
output, reproducing the "Batch process the whole cohort" cell of the notebook.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from .analysis import assign_morphotypes
from .config import Config
from .discovery import discover_images, load_animal_key, load_scale_table
from .segment import process_image


@dataclass
class Phase1Result:
    img_df: pd.DataFrame
    objs_df: pd.DataFrame
    n_images: int
    n_missing_scale: int
    n_unknown_animal: int
    scale: dict = field(default_factory=dict)
    animal_lookup: dict = field(default_factory=dict)


def run_phase1(
    cfg: Config,
    *,
    do_morphotypes: bool = True,
    progress: Callable[[str], None] = print,
) -> Phase1Result:
    """Process the whole cohort and write per-image / per-object CSVs.

    Writes ``per_image_summary.csv`` and ``per_object_features.csv`` under
    ``cfg.out_dir`` (created if needed) and returns the in-memory frames plus the
    lookup tables, so callers can run stats/plots without recomputing.
    """
    if cfg.data_dir is None:
        raise ValueError("cfg.data_dir is required for Phase 1")

    image_paths = discover_images(cfg.data_dir)
    if not image_paths:
        raise SystemExit(
            f"No images found under {cfg.data_dir} — check --data."
        )
    scale = load_scale_table(cfg.scale_table)
    if scale:
        progress(f"Loaded {len(scale)} per-image scales from {cfg.scale_table}")
    else:
        progress(
            f"No scale table at {cfg.scale_table} — run `prion calibrate` first; "
            "areas will be reported in PIXELS."
        )
    animal_lookup = load_animal_key(cfg.animal_key)
    if animal_lookup:
        progress(f"Loaded animal key from {cfg.animal_key}")

    thr_label = "Otsu (per-image)" if cfg.dab_threshold is None else cfg.dab_threshold
    progress(
        f"Processing {len(image_paths)} images at DAB_THRESHOLD={thr_label} ..."
    )

    rows, objs = [], []
    n_missing_scale = 0
    for i, p in enumerate(image_paths):
        try:
            summary, odf = process_image(p, cfg, scale, animal_lookup)
            rows.append(summary)
            if isinstance(summary["um_per_px"], float) and np.isnan(summary["um_per_px"]):
                n_missing_scale += 1
            if len(odf):
                objs.append(odf)
        except Exception as e:  # one bad image must not kill the batch
            progress(f"[skip] {p.name}: {e}")
        if (i + 1) % 25 == 0:
            progress(f"  processed {i + 1}/{len(image_paths)}")

    img_df = pd.DataFrame(rows)
    objs_df = pd.concat(objs, ignore_index=True) if objs else pd.DataFrame()

    if do_morphotypes and len(objs_df):
        result = assign_morphotypes(objs_df, cfg)
        if result is not None:
            objs_df = result.objects

    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    img_df.to_csv(cfg.out_dir / "per_image_summary.csv", index=False)
    objs_df.to_csv(cfg.out_dir / "per_object_features.csv", index=False)

    n_unknown = int((img_df["animal"] == "UNKNOWN").sum()) if len(img_df) else 0
    progress(
        f"DONE. {len(img_df)} images, {len(objs_df)} objects -> {cfg.out_dir.resolve()}"
    )
    if n_missing_scale:
        progress(
            f"  NOTE: {n_missing_scale} image(s) had no scale; their areas are in pixels."
        )
    if n_unknown and len(img_df):
        progress(
            f"  NOTE: {n_unknown} image(s) have animal=UNKNOWN; "
            "supply --animal-key for animal-level statistics."
        )

    return Phase1Result(
        img_df=img_df,
        objs_df=objs_df,
        n_images=len(img_df),
        n_missing_scale=n_missing_scale,
        n_unknown_animal=n_unknown,
        scale=scale,
        animal_lookup=animal_lookup,
    )
