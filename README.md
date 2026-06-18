# prion_ml_pipeline

[![CI](https://github.com/ryan-eastman/prion_ml_pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/ryan-eastman/prion_ml_pipeline/actions/workflows/ci.yml)

Measure prion (PrP) burden in DAB/IHC brain photomicrographs and compare groups
(deer / elk vs. control) — from a folder of `.tif` images to result tables and
figures, with **one command** and no code editing.

You give it a folder of images; it gives you, per image: the **% of tissue that
is PrP-positive**, how many deposits there are, their sizes/shapes, and group
comparisons. CPU only — it runs on a normal laptop.

---

## Quick start

### 1. Install Python (skip if you already have it)

You need **Python 3.10 or newer** (3.11+ recommended; the exact-reproducible
install below requires 3.11+). If you don't have it, install it from
[python.org/downloads](https://www.python.org/downloads/) (or
[Anaconda](https://www.anaconda.com/download)). To check what you have:

```bash
python --version      # if that says "command not found", try: python3 --version
```

> On macOS/Linux the command is often **`python3`** (not `python`). Use whichever
> one printed a version — substitute it everywhere below.

### 2. Get the code

This repository is **private**, so you need to be added as a collaborator and
signed in to GitHub first (ask the maintainer for access). Then either:

**Option A — download a ZIP (no Git needed).** On the repository's GitHub page,
click the green **Code** button → **Download ZIP**, unzip it, and open a terminal
in the unzipped folder.

**Option B — clone with Git.** Requires Git ([git-scm.com/downloads](https://git-scm.com/downloads);
on macOS the first `git` command may prompt you to install Apple's Command Line
Tools — click Install):

```bash
git clone https://github.com/ryan-eastman/prion_ml_pipeline.git
cd prion_ml_pipeline
```

### 3. Install it

```bash
python -m venv .venv          # make an isolated environment (or: python3 -m venv .venv)
```

Now **activate** it (this is the one command that differs by operating system):

| Your computer | Command to activate |
|---|---|
| macOS / Linux | `source .venv/bin/activate` |
| Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |
| Windows (Command Prompt) | `.venv\Scripts\activate.bat` |

Then install:

```bash
pip install -e .
```

That's it — you now have a `prion` command. (Using Anaconda instead of `venv`?
See [Installing with conda](#installing-with-conda) below.)

### 4. Check it works — run the demo

```bash
prion demo
```

This invents a tiny fake dataset and runs the whole pipeline on it, so you can
confirm everything is installed correctly **without needing any of your own
images yet**. It writes results into a new `prion_demo/` folder and prints the
exact path.

### 5. Run it on your own images

Put your `.tif`/`.tiff` images in a folder (sub-folders are fine), then:

```bash
prion run --data /path/to/your/images --stats --plots
```

That single command reads the scale from each image, measures PrP burden and
deposit shapes, compares groups, and saves figures. Results land in `outputs/`.

> **Tip — animal-level statistics.** Add `--animal-key animal_key.csv` if you
> have a file linking each image to an animal. The CSV needs at least an `image`
> column and an `animal` column (extra columns are ignored):
>
> ```csv
> image,animal
> GtDeer_treatment_cerebellum_4x_01.tif,J2009
> GtDeer_treatment_cerebellum_4x_02.tif,J2065
> ```
>
> A ready-made example ships at [`notebooks/animal_key.csv`](notebooks/animal_key.csv).
> Without it, group comparisons are image-level and exploratory only.

---

## Understanding your results

`prion run` writes results to an **`outputs/`** folder (change it with `--out`).
If you ran `prion demo`, the same files are under **`prion_demo/outputs/`** (the
demo prints the exact path). Either way you get two tables:

**`per_image_summary.csv`** — one row per image:

| Column | What it means |
|---|---|
| `pct_area_burden` | **% of tissue that is PrP-positive** — the headline number. |
| `n_objects` | How many separate PrP deposits were detected. |
| `density_per_mm2` | Deposits per mm² of tissue. |
| `mean_area_um2` | Average deposit size, in µm². |
| `median_circularity` | How round the deposits are (1.0 = perfect circle). |
| `um_per_px` | The image's scale (microns per pixel). |
| `species`, `condition`, `region`, `animal` | Read from the file name / animal key. |

The CSV also includes `image`, `magnification`, `image_id`, `tissue_mm2` (measured
tissue area), and `dab_threshold` (the cutoff used).

**`per_object_features.csv`** — one row per individual deposit (area, shape,
location, and a `morphotype` label: *compact* / *intermediate* / *diffuse*).

With `--plots` you also get an `outputs/figures/` folder (burden by region,
morphotype clusters, spatial clustering).

---

## Common options

You rarely need more than these. Run `prion run --help` for the full list.

| Option | What it does |
|---|---|
| `--stats` | Print a statistical comparison of the groups. |
| `--plots` | Save summary figures (PNG). |
| `--animal-key FILE.csv` | Link images → animals for proper animal-level stats. |
| `--dab-threshold 0.05` | How dark a pixel must be to count as PrP-positive. Higher = stricter. Use `prion sweep` to choose. |
| `--out FOLDER` | Where to save results (default: `outputs`). |

---

## Troubleshooting

**`prion: command not found`** — your environment isn't activated. Re-run the
activate command from step 3 (you must do this each time you open a new terminal).

**"No images found under … — check --data"** — the `--data` path is wrong, or the
folder has no `.tif`/`.tiff` files. Double-check the path; sub-folders are searched
automatically.

**"--animal-key file does not exist" / "must have 'image' and 'animal' columns"** —
check the path you passed, and that the CSV has columns named exactly `image` and
`animal` (see the example in step 5).

**"… image(s) had no scale; their areas are in pixels"** — those images don't carry
a microns-per-pixel value in their metadata, so sizes can't be converted to µm.
Most measurements still work; areas for those images are just in pixels.

**"… image(s) have animal=UNKNOWN"** — those images aren't listed in your
`--animal-key` file (or you didn't pass one). Add them to enable animal-level stats.

**"the animal-level mixed-effects model could not be fit"** — your design is
unbalanced/confounded (e.g. every control is the same species). The tool falls
back to a simpler per-region test automatically; this is expected, not an error.

---

## How it works (for the curious)

Three steps, which `prion run` chains together for you:

1. **Calibrate** (`prion calibrate`) — read microns-per-pixel from each TIFF's
   metadata into a scale table.
2. **Phase 1** (`prion phase1`) — separate brown DAB staining from tissue, measure
   the PrP-positive area and each deposit's size/shape, cluster deposits into
   morphotypes, and compare groups.
3. (Optional) **Sweep** (`prion sweep`) — try a range of DAB thresholds on a few
   control vs. treatment images to help you pick a good cutoff.

A *fixed* DAB threshold is used on purpose (not a per-image one) so that burden is
comparable across images and groups.

---

## Advanced

### Configuration file

Every option has a sensible default. To keep settings in a file instead of typing
flags, copy [`configs/default.yaml`](configs/default.yaml), edit it, and pass it:

```bash
prion run --data /path/to/images --config my_settings.yaml
```

Precedence: built-in defaults → `--config` file → explicit command-line flags.

### Installing with conda

```bash
conda env create -f environment.yml
conda activate prion
pip install -e .
```

### Exact, reproducible install

`pip install -e .` resolves compatible dependency versions for your platform. For
the *exact* versions this was validated against (lockfile; validated on Python
3.13 / macOS arm64 — some pins require Python ≥ 3.11):

```bash
pip install -r requirements.txt
pip install -e .
```

### Notebooks

The original analysis notebooks are kept under [`notebooks/`](notebooks/) for
reference (`pip install -e ".[notebooks]"` to run them). The `prion` package is
the supported, deployable interface.

---

## Notes on scientific rigour

- The **animal** is the experimental unit. Without `--animal-key`, group
  comparisons are image-level and **exploratory only** (pseudoreplicated).
- A *fixed* DAB threshold (not per-image Otsu) keeps burden comparable across
  images and groups.
- For publication-grade spatial statistics, use R `spatstat` (`Kinhom` / `pcf`)
  with edge correction rather than the bundled Ripley's L.
- The GPU deep-learning stage (StarDist) from the original project is
  intentionally **not** included here.

## For developers

```bash
pip install -e ".[dev]"
pytest
```

Cross-platform CI (Linux / macOS / Windows, Python 3.10–3.13) runs the suite on
every push. See [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## License

MIT — see [LICENSE](LICENSE).
