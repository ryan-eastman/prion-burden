# prion_ml_pipeline

[![CI](https://github.com/ryan-eastman/prion_ml_pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/ryan-eastman/prion_ml_pipeline/actions/workflows/ci.yml)

This tool measures prion (PrP) burden in stained brain images. You give it a
folder of microscope images (`.tif` files), and it tells you, for each image,
how much of the tissue is prion-positive, how many deposits there are, and the
size and shape of those deposits. It can then compare your groups (for example,
deer versus elk versus control). It runs on a normal laptop.

You do not need to know how to write code to use it. You type a few short
commands, which are all shown below.

## What you need

- A computer running Windows, macOS, or Linux.
- Python version 3.10 or newer (3.11 or newer is best). Step 1 shows how to get it.
- A folder of microscope images saved as `.tif` or `.tiff` files.

## Quick start

### Step 1. Install Python (skip if you already have it)

Get Python from [python.org/downloads](https://www.python.org/downloads/) or from
[Anaconda](https://www.anaconda.com/download). To see if you already have it, open
a terminal and type:

```bash
python --version
```

If that says "command not found", try `python3 --version` instead. On macOS and
Linux the command is usually `python3`. Use whichever one shows a version number,
and use that same word (`python` or `python3`) everywhere below.

### Step 2. Get the code

This project is private, so first ask the project owner to give you access, and
sign in to your GitHub account. Then choose one of these:

- **Download a ZIP (no extra software needed).** On the project's GitHub page,
  click the green **Code** button, then **Download ZIP**. Unzip the file, then
  open a terminal inside the unzipped folder.
- **Or use Git.** Install Git from [git-scm.com/downloads](https://git-scm.com/downloads)
  if you do not have it (on macOS, the first `git` command may offer to install
  Apple's Command Line Tools, which is fine). Then run:

  ```bash
  git clone https://github.com/ryan-eastman/prion_ml_pipeline.git
  cd prion_ml_pipeline
  ```

### Step 3. Install the tool

First make a separate workspace for it (called a virtual environment):

```bash
python -m venv .venv
```

Then turn that workspace on. The command is different on each system:

| Your computer | Command to turn it on |
|---|---|
| macOS or Linux | `source .venv/bin/activate` |
| Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |
| Windows (Command Prompt) | `.venv\Scripts\activate.bat` |

Finally, install the tool:

```bash
pip install -e .
```

You now have a command called `prion`. (Prefer Anaconda? See
[Install with conda](#install-with-conda) below.)

### Step 4. Check that it works

```bash
prion demo
```

This makes a small set of example images and runs the whole tool on them, so you
can confirm everything is installed correctly before using your own images. It
saves the results in a new folder called `prion_demo` and prints the exact
location.

### Step 5. Run it on your own images

Put your `.tif` images in one folder (sub-folders are fine), then run:

```bash
prion run --data /path/to/your/images
```

That one command reads the scale from each image, measures the prion burden and
the deposit shapes, compares your groups, and saves tables and figures. The
results are saved in a folder called `outputs`.

To get stronger statistics, add an animal key file that links each image to an
animal (see the next section):

```bash
prion run --data /path/to/your/images --animal-key animal_key.csv
```

## The animal key file (optional but recommended)

Statistics are most reliable when each animal counts once, not each image. To do
that, give the tool a simple spreadsheet (a `.csv` file) that lists, for each
image, which animal it came from. It needs a column named `image` and a column
named `animal`. Extra columns are ignored.

```csv
image,animal
GtDeer_treatment_cerebellum_4x_01.tif,J2009
GtDeer_treatment_cerebellum_4x_02.tif,J2065
```

A ready-made example is included at [`notebooks/animal_key.csv`](notebooks/animal_key.csv);
you can open it in Excel and use it as a template.

## Understanding your results

`prion run` saves everything in a folder called `outputs` (change the name with
`--out`). If you ran `prion demo`, the same files are inside `prion_demo/outputs`
instead. You get two tables and a set of figures.

**`per_image_summary.csv`** has one row per image:

| Column | What it means |
|---|---|
| `pct_area_burden` | The percent of the tissue that is prion-positive. This is the main number. |
| `n_objects` | How many separate deposits were found. |
| `density_per_mm2` | Deposits per square millimeter of tissue. |
| `mean_area_um2` | Average deposit size, in square microns. |
| `median_circularity` | How round the deposits are (1.0 is a perfect circle). |
| `um_per_px` | The image scale (microns per pixel). |
| `species`, `condition`, `region`, `animal` | Read from the file name and the animal key. |

The table also includes `image`, `magnification`, `image_id`, `tissue_mm2` (how
much tissue was measured), and `dab_threshold` (the cutoff that was used).

**`per_object_features.csv`** has one row for every single deposit: its size,
shape, location, and a shape type (compact, intermediate, or diffuse).

The **`figures`** folder has charts of burden by brain region, the deposit shape
types, and how clustered the deposits are.

## Options

You usually do not need any of these. Type `prion run --help` to see them all.

| Option | What it does |
|---|---|
| `--animal-key FILE.csv` | Links each image to an animal for stronger statistics. |
| `--out FOLDER` | Where to save the results (default is `outputs`). |
| `--dab-threshold 0.05` | How dark a pixel must be to count as prion-positive. A higher number is stricter. Use `prion sweep` to help pick one. |
| `--no-plots` | Do not save the figures. |
| `--no-stats` | Do not print the group comparison. |

## If something goes wrong

**`prion: command not found`**: your workspace is turned off. Run the turn-on
command from step 3 again. You need to do this each time you open a new terminal.

**`No images found under ... check --data`**: the folder path is wrong, or the
folder has no `.tif` or `.tiff` files. Check the path. Sub-folders are searched
for you.

**`--animal-key file does not exist`** or **`must have 'image' and 'animal'
columns`**: check the file path, and make sure the spreadsheet has columns named
exactly `image` and `animal` (see the example above).

**`some image(s) had no scale; their areas are in pixels`**: those images do not
store a microns-per-pixel value, so their sizes cannot be converted to microns.
Most results still work; only those images report sizes in pixels.

**`some image(s) have animal=UNKNOWN`**: those images are not listed in your
animal key file. Add them to include them in the animal-level statistics.

**`the animal-level model could not be fit`**: this happens when the groups are
unbalanced (for example, every control is the same species). The tool
automatically falls back to a simpler comparison. This is expected.

## How it works

`prion run` does two steps for you:

1. **Read the scale.** It reads the microns-per-pixel value stored inside each
   image. (`prion calibrate` does only this step.)
2. **Measure and compare.** It separates the brown stain from the tissue,
   measures how much is prion-positive, measures each deposit's size and shape,
   sorts the deposits into shape types, and compares the groups. (`prion phase1`
   does only this step.)

`prion sweep` is a helper that tries several brightness cutoffs on a few images
so you can choose a good one.

The brightness cutoff is the same for every image on purpose, so that results
can be compared fairly across images and groups.

## Notes for careful analysis

- The animal, not the image, is the true unit. Without an animal key, group
  comparisons treat each image as independent, which is only a rough, exploratory
  result.
- A single fixed cutoff (not an automatic per-image one) keeps results comparable
  across images and groups.
- For publication-quality spatial statistics, use the R package `spatstat`
  (`Kinhom` or `pcf`) with edge correction.

## Advanced

### Settings file

Every option has a sensible default. To keep your settings in a file instead of
typing them each time, copy [`configs/default.yaml`](configs/default.yaml), edit
it, and pass it with `--config`:

```bash
prion run --data /path/to/images --config my_settings.yaml
```

### Install with conda

```bash
conda env create -f environment.yml
conda activate prion
pip install -e .
```

### Exact, reproducible install

`pip install -e .` picks dependency versions that fit your computer. To install
the exact versions this was tested with (validated on Python 3.13; note that
some of these versions require Python 3.11 or newer):

```bash
pip install -r requirements.txt
pip install -e .
```

### Notebooks

The original analysis notebooks are in the [`notebooks/`](notebooks/) folder for
reference. The `prion` command is the supported way to run the tool.

## For developers

```bash
pip install -e ".[dev]"
pytest
```

Automated tests run on Windows, macOS, and Linux (Python 3.10 through 3.13) on
every push. See [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## License

MIT. See [LICENSE](LICENSE).
