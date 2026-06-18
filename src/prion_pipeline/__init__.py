"""prion_pipeline — CWD/prion PrP-burden quantification (Phase 0 + Phase 1).

A deployable, config-driven refactor of the original Jupyter notebooks:

* **Phase 0 / calibrate** — recover µm/px from each TIFF's embedded metadata
  (Olympus SIS, OME-XML, ImageJ, or resolution tags) into a ``scale_table.csv``.
* **Phase 1 / classical** — DAB optical-density burden, per-object morphometry,
  morphotype clustering, spatial spread (Ripley's L) and group statistics. CPU
  only; no training and no GPU.

The science is unchanged from the notebooks; this package only makes paths and
parameters configurable and exposes a ``prion`` command-line interface.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
