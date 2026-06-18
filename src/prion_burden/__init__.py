"""prion_burden: measure prion (PrP) burden in stained brain images.

A deployable, config-driven refactor of the original Jupyter notebooks:

* **calibrate** recovers µm/px from each TIFF's embedded metadata
  (Olympus SIS, OME-XML, ImageJ, or resolution tags) into a ``scale_table.csv``.
* **measure** computes DAB optical-density burden, per-object morphometry,
  morphotype clustering, spatial spread (Ripley's L) and group statistics.

Runs on a normal computer (CPU). The science is unchanged from the notebooks;
this package only makes paths and parameters configurable and exposes a
``prion`` command-line interface.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
