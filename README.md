# prion_ml_pipeline

Quantify PrP (prion) burden in DAB/IHC photomicrographs of cervidized-mouse
brain (CWD: GtDeer / GtElk treatment vs. WT control). This repository packages
**Phase 0** (scale calibration) and **Phase 1** (classical, CPU-only burden +
morphometry + spatial statistics) as an installable Python package with a
`prion` command-line interface.

> The science is a faithful port of the original Jupyter notebooks
> ([`notebooks/`](notebooks/)); this package makes paths and parameters
> configurable so the pipeline runs unchanged on any machine. The GPU deep-learning
> stage (StarDist) is intentionally **not** included.

## What it measures

1. **Burden** — % PrP-positive tissue area (fixed DAB optical-density cutoff so
   values are comparable across images and groups), object count, density per mm².
2. **Morphometry** — per-object area, circularity, solidity, aspect ratio; KMeans
   morphotype typing (compact / intermediate / diffuse).
3. **Spread** — Ripley's L(r) clustering vs. complete spatial randomness.
4. **Group stats** — mixed-effects model with animal as the random effect when an
   animal key is supplied; otherwise an exploratory per-region Kruskal–Wallis.

## Install

Requires Python ≥ 3.10. From a fresh virtual environment:

```bash
git clone https://github.com/ryan-eastman/prion_ml_pipeline.git
cd prion_ml_pipeline

python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate

# Reproducible install — exact lockfile, validated on Python 3.13 / macOS arm64.
# (Some pins, e.g. numpy 2.4.6, require Python >= 3.11; on Python 3.10 or other
#  platforms use the flexible install below instead.)
pip install -r requirements.txt
pip install -e .

# …or a flexible, cross-platform install (dependency bounds from pyproject.toml):
pip install -e ".[dev]"
```

This installs the `prion` console command.

## Usage

The pipeline is three steps. Point `--data` at a directory of `.tif`/`.tiff`
images (searched recursively; byte-identical duplicate filenames are ignored).

```bash
# 0) Recover µm/px from each TIFF's embedded metadata -> scale_table.csv
prion calibrate --data /path/to/prion_images

# 1) Burden + morphometry + morphotypes -> per_image_summary.csv, per_object_features.csv
prion phase1 --data /path/to/prion_images \
    --animal-key notebooks/animal_key.csv \
    --stats --plots

# (optional) Calibrate the DAB threshold: WT control should fall to ~0% burden
prion sweep --data /path/to/prion_images --out outputs/threshold_sweep.csv --plots
```

Outputs land in `outputs/` (and `outputs_calib/scale_table.csv`); figures, if
requested, in `outputs/figures/`. None of these are committed (see `.gitignore`).

### Configuration

Every parameter has a sensible default. Override them with flags, or keep a YAML
config and pass `--config`:

```bash
cp configs/default.yaml my_run.yaml      # edit dab_threshold, regions, etc.
prion phase1 --data /path/to/images --config my_run.yaml
```

Precedence: built-in defaults → `--config` YAML → explicit CLI flags. Run
`prion <command> --help` for the full flag list.

| Parameter | Flag | Default | Notes |
|---|---|---|---|
| DAB threshold | `--dab-threshold` | `0.05` | Fixed cutoff; calibrate with `prion sweep`. |
| Min object area | `--min-object-um2` | `50.0` | 4× is low-resolution. |
| Animal key | `--animal-key` | none | Enables animal-level mixed-effects stats. |
| Target µm/px | `--target-um-per-px` | none | Set only for **mixed**-magnification cohorts. |

## Outputs

- `outputs_calib/scale_table.csv` — `image, um_per_px`
- `outputs/per_image_summary.csv` — one row per image (burden %, n objects,
  density, mean area, median circularity, …)
- `outputs/per_object_features.csv` — one row per detected deposit (area, shape,
  centroid, morphotype, …)

## Notes on rigour

- The **animal** is the experimental unit. Without `--animal-key`, group
  comparisons are image-level, pseudoreplicated, and **exploratory only**.
- A *fixed* DAB threshold (not per-image Otsu) is used on purpose so burden is
  comparable across images and groups.
- For publication-grade inhomogeneous spatial statistics, use R `spatstat`
  (`Kinhom` / `pcf`) with edge correction rather than the bundled Ripley's L.

## Development

```bash
pip install -e ".[dev]"
pytest
```

The notebooks under [`notebooks/`](notebooks/) are kept for reference and are
paired to `.py` via [jupytext]; install `".[notebooks]"` to run them.

[jupytext]: https://jupytext.readthedocs.io/

## License

MIT — see [LICENSE](LICENSE).
