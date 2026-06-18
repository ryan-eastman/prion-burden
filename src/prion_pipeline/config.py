"""Configuration for the prion pipeline.

The original notebooks kept their parameters in a hand-edited "CONFIG — EDIT
THIS CELL" block with absolute paths baked in. Here those same parameters live
in a dataclass that can be loaded from a YAML file and overridden on the command
line, so the pipeline runs unchanged on any machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, asdict
from pathlib import Path
from typing import Any

import numpy as np

# Default biological metadata vocabulary (matches the notebooks).
DEFAULT_REGIONS = ["cerebellum", "hippocampus", "midbrain", "septum"]
DEFAULT_MAGS = ["4x"]
IMG_EXTS = {".tif", ".tiff"}


@dataclass
class Config:
    """Runtime parameters for calibration and Phase 1.

    Every field has a default that reproduces the notebook behaviour; only
    ``data_dir`` is genuinely required at run time (validated by the CLI).
    """

    # --- paths -------------------------------------------------------------
    data_dir: Path | None = None
    out_dir: Path = Path("outputs")
    scale_table: Path = Path("outputs_calib/scale_table.csv")
    animal_key: Path | None = None

    # --- scale handling ----------------------------------------------------
    # None keeps native per-image scale (no resample); set a value only for a
    # MIXED-magnification cohort that must be standardised to one µm/px.
    target_um_per_px: float | None = None

    # --- segmentation ------------------------------------------------------
    # FIXED DAB optical-density cutoff for "PrP-positive". A fixed value (not a
    # per-image Otsu) is essential so burden is comparable across images/groups.
    # Set to ``None`` to fall back to per-image Otsu (exploratory only).
    dab_threshold: float | None = 0.05
    min_object_um2: float = 50.0       # 4x is low-res; tune on the sanity image
    min_peak_dist: int = 3             # watershed seed spacing (px)

    # --- analysis ----------------------------------------------------------
    n_morphotypes: int = 3
    random_state: int = 0

    # --- metadata vocabulary ----------------------------------------------
    regions: list[str] = field(default_factory=lambda: list(DEFAULT_REGIONS))
    mags: list[str] = field(default_factory=lambda: list(DEFAULT_MAGS))

    # ----------------------------------------------------------------------
    def __post_init__(self) -> None:
        # Coerce path-like fields so callers may pass plain strings.
        for name in ("data_dir", "out_dir", "scale_table", "animal_key"):
            val = getattr(self, name)
            if val is not None and not isinstance(val, Path):
                setattr(self, name, Path(val))
        # ``target_um_per_px`` may arrive as the string "none"/"null" from YAML.
        if isinstance(self.target_um_per_px, str):
            self.target_um_per_px = (
                None if self.target_um_per_px.lower() in ("none", "null", "")
                else float(self.target_um_per_px)
            )

    # ----------------------------------------------------------------------
    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        """Load a config from a YAML file (unknown keys are rejected loudly)."""
        import yaml

        with open(path, "r") as fh:
            data = yaml.safe_load(fh) or {}
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(
                f"Unknown config key(s): {sorted(unknown)}. "
                f"Valid keys: {sorted(known)}"
            )
        return cls(**data)

    def merge_overrides(self, **overrides: Any) -> "Config":
        """Return a copy with any non-``None`` overrides applied.

        ``None`` means "not supplied on the CLI", so it never clobbers a value
        already set in the YAML config or the dataclass default.
        """
        data = asdict(self)
        for key, val in overrides.items():
            if val is not None:
                data[key] = val
        return Config.from_dict(data)

    def effective_target_um_per_px(self) -> float:
        """``target_um_per_px`` as a float, mapping ``None`` to NaN for math."""
        return np.nan if self.target_um_per_px is None else float(self.target_um_per_px)
