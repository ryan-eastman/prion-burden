"""Command-line interface: ``prion demo | run | calibrate | phase1 | sweep``.

New users should start with ``prion demo`` (runs everything on built-in
synthetic data) and then ``prion run --data <folder>`` (the one-command path:
calibrate + Phase 1). ``calibrate`` / ``phase1`` / ``sweep`` are the individual
steps for finer control.

Configuration precedence (low -> high): dataclass defaults < ``--config`` YAML
< explicit command-line flags. This replaces the notebooks' hand-edited CONFIG
cells, so the same code runs on any machine without edits.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import Config


# --- shared options --------------------------------------------------------
def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--data", dest="data_dir", type=Path,
                   help="Image directory (searched recursively).")
    p.add_argument("--config", type=Path,
                   help="YAML config file; CLI flags override its values.")


def _build_config(args: argparse.Namespace, **overrides) -> Config:
    cfg = Config.from_yaml(args.config) if getattr(args, "config", None) else Config()
    return cfg.merge_overrides(**overrides)


def _validate_inputs(cfg: Config, *, check_animal_key: bool) -> int | None:
    """Friendly, consistent checks for the common input mistakes.

    Returns an exit code (2) with a clear stderr message on the first problem,
    or ``None`` if everything looks usable.
    """
    if cfg.data_dir is None:
        print("error: --data is required (the folder with your .tif/.tiff images)",
              file=sys.stderr)
        return 2
    if not cfg.data_dir.exists():
        print(f"error: --data folder does not exist: {cfg.data_dir}", file=sys.stderr)
        return 2
    from .discovery import discover_images

    if not discover_images(cfg.data_dir):
        print(f"error: no .tif/.tiff images found under {cfg.data_dir} — check --data.",
              file=sys.stderr)
        return 2
    if check_animal_key and cfg.animal_key is not None and not cfg.animal_key.exists():
        print(f"error: --animal-key file does not exist: {cfg.animal_key}", file=sys.stderr)
        return 2
    return None


# --- calibrate -------------------------------------------------------------
def cmd_calibrate(args: argparse.Namespace) -> int:
    cfg = _build_config(
        args,
        data_dir=args.data_dir,
        scale_table=args.out,
    )
    rc = _validate_inputs(cfg, check_animal_key=False)
    if rc is not None:
        return rc
    from .calibrate import build_scale_table

    out = cfg.scale_table
    mt = build_scale_table(cfg.data_dir, out)
    got = int(mt["um_per_px"].notna().sum())
    print(f"Scale recovered for {got}/{len(mt)} images -> {out}")
    missing = mt[mt["um_per_px"].isna()]["image"].tolist()
    if missing:
        print(f"{len(missing)} image(s) have NO embedded scale (will fall back to pixels):")
        print("  " + ", ".join(missing[:20]) + (" ..." if len(missing) > 20 else ""))
    return 0


# --- phase1 ----------------------------------------------------------------
def cmd_phase1(args: argparse.Namespace) -> int:
    cfg = _build_config(
        args,
        data_dir=args.data_dir,
        out_dir=args.out,
        scale_table=args.scale_table,
        animal_key=args.animal_key,
        dab_threshold=args.dab_threshold,
        min_object_um2=args.min_object_um2,
        target_um_per_px=args.target_um_per_px,
    )
    rc = _validate_inputs(cfg, check_animal_key=True)
    if rc is not None:
        return rc

    from .pipeline import run_phase1

    result = run_phase1(cfg, do_morphotypes=not args.no_morphotypes)
    _postprocess(cfg, result, do_stats=args.stats, do_plots=args.plots)
    return 0


def _postprocess(cfg, result, *, do_stats: bool, do_plots: bool) -> None:
    """Optional group statistics + figures, shared by `phase1` and `run`."""
    if do_stats and len(result.img_df):
        from .analysis import group_comparison

        rep = group_comparison(result.img_df, cfg)
        print("\n=== Group comparison ===")
        if rep["method"] == "mixedlm":
            print(f"Mixed-effects model (animal random effect), "
                  f"{rep['n_animals']} animals:\n{rep['summary']}")
        else:
            print(rep["note"])
            if rep.get("mixedlm_error"):
                print("  (the animal-level mixed-effects model could not be fit on "
                      "this dataset, so a simpler per-region test is shown instead.)")
            for reg, r in rep.get("per_region", {}).items():
                print(f"  {reg:12s} Kruskal-Wallis H={r['H']:.2f} p={r['p']:.3g} groups={r['groups']}")

    if do_plots and len(result.img_df):
        _write_plots(cfg, result)


def _write_plots(cfg, result) -> None:
    from . import plots
    from .analysis import assign_morphotypes, spread_for_image

    fig_dir = cfg.out_dir / "figures"
    written = [plots.burden_by_region(result.img_df, cfg, fig_dir / "burden_by_region.png")]
    if len(result.objs_df):
        mr = assign_morphotypes(result.objs_df, cfg)
        if mr is not None:
            written.append(plots.morphotype_pca(mr, fig_dir / "morphotypes_pca.png"))
    # Ripley's L on the image with the most objects.
    if len(result.img_df):
        top = result.img_df.sort_values("n_objects", ascending=False)["image"].iloc[0]
        path = next((p for p in cfg.data_dir.rglob(top)), None)
        if path is not None:
            spread = spread_for_image(path, cfg, result.scale)
            if spread is not None:
                written.append(plots.ripley(spread, fig_dir / "ripley_L.png"))
    print(f"\nWrote {len(written)} figure(s) to {fig_dir.resolve()}")


# --- run (one-command: calibrate + phase1) ---------------------------------
def cmd_run(args: argparse.Namespace) -> int:
    cfg = _build_config(
        args,
        data_dir=args.data_dir,
        out_dir=args.out,
        scale_table=args.scale_table,
        animal_key=args.animal_key,
        dab_threshold=args.dab_threshold,
        min_object_um2=args.min_object_um2,
        target_um_per_px=args.target_um_per_px,
    )
    rc = _validate_inputs(cfg, check_animal_key=True)
    if rc is not None:
        return rc
    # Keep a single `run` self-contained: unless the user pointed --scale-table
    # elsewhere, put the scale table inside the chosen --out folder (not the cwd).
    if args.scale_table is None:
        cfg = cfg.merge_overrides(scale_table=cfg.out_dir / "scale_table.csv")

    from .calibrate import build_scale_table
    from .pipeline import run_phase1

    print("Step 1/2: reading the scale (µm per pixel) from each image ...")
    mt = build_scale_table(cfg.data_dir, cfg.scale_table)
    got = int(mt["um_per_px"].notna().sum())
    print(f"  scale found for {got}/{len(mt)} images -> {cfg.scale_table}")

    print("Step 2/2: measuring PrP burden + morphometry ...")
    result = run_phase1(cfg, do_morphotypes=not args.no_morphotypes)
    _postprocess(cfg, result, do_stats=args.stats, do_plots=args.plots)

    print("\nAll done. Your results are here:")
    print(f"  per-image summary : {(cfg.out_dir / 'per_image_summary.csv').resolve()}")
    print(f"  per-object table  : {(cfg.out_dir / 'per_object_features.csv').resolve()}")
    print(f"  scale table       : {cfg.scale_table.resolve()}")
    if args.plots:
        print(f"  figures           : {(cfg.out_dir / 'figures').resolve()}")
    return 0


# --- demo (run everything on built-in synthetic data) ----------------------
def cmd_demo(args: argparse.Namespace) -> int:
    root = args.out or Path("prion_demo")
    from .calibrate import build_scale_table
    from .demo import make_synthetic_cohort
    from .pipeline import run_phase1

    print(f"Creating a tiny synthetic dataset in {root.resolve()} (no real data needed) ...")
    data, key = make_synthetic_cohort(root)
    cfg = Config(
        data_dir=data,
        out_dir=root / "outputs",
        scale_table=root / "outputs_calib" / "scale_table.csv",
        animal_key=key,
    )
    build_scale_table(cfg.data_dir, cfg.scale_table)
    result = run_phase1(cfg, do_morphotypes=True)
    _postprocess(cfg, result, do_stats=True, do_plots=not args.no_plots)

    print("\n" + "=" * 64)
    print("The demo worked — your installation is good.")
    print("It ran the REAL pipeline on FAKE images. Note how the control")
    print("animals show low burden (~1%) and the 'treatment' animals show")
    print("clearly more (~2-5%).")
    print(f"\nLook at the results in: {cfg.out_dir.resolve()}")
    print("\nNext, run it on your own images:")
    print("  prion run --data /path/to/your/images --stats --plots")
    print("=" * 64)
    return 0


# --- sweep -----------------------------------------------------------------
def cmd_sweep(args: argparse.Namespace) -> int:
    cfg = _build_config(
        args,
        data_dir=args.data_dir,
        scale_table=args.scale_table,
        animal_key=args.animal_key,
    )
    rc = _validate_inputs(cfg, check_animal_key=True)
    if rc is not None:
        return rc

    from .analysis import threshold_sweep
    from .discovery import discover_images, load_animal_key, load_scale_table

    image_paths = discover_images(cfg.data_dir)
    scale = load_scale_table(cfg.scale_table)
    animal_lookup = load_animal_key(cfg.animal_key)
    pivot = threshold_sweep(image_paths, cfg, scale, animal_lookup, k=args.k)
    if pivot.empty:
        print("No control/treatment images sampled — nothing to sweep.")
        return 0
    print(pivot.round(3).to_string())
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        pivot.to_csv(args.out)
        print(f"\nWrote sweep table -> {args.out}")
        if args.plots:
            from . import plots

            fig = plots.threshold_sweep(pivot, cfg, args.out.with_suffix(".png"))
            print(f"Wrote sweep figure -> {fig}")
    return 0


# --- parser ----------------------------------------------------------------
def _add_phase1_flags(p: argparse.ArgumentParser) -> None:
    """Flags shared by the `phase1` and `run` subcommands."""
    p.add_argument("--out", dest="out", type=Path, default=None,
                   help="Output directory for CSVs/figures (default: outputs).")
    p.add_argument("--scale-table", type=Path, default=None,
                   help="Per-image µm/px table (default: outputs_calib/scale_table.csv).")
    p.add_argument("--animal-key", type=Path, default=None,
                   help="CSV mapping image -> animal id (enables animal-level stats).")
    p.add_argument("--dab-threshold", type=float, default=None,
                   help="Fixed DAB optical-density cutoff (default 0.05; comparable across images).")
    p.add_argument("--min-object-um2", type=float, default=None,
                   help="Minimum object area in µm^2 (default 50).")
    p.add_argument("--target-um-per-px", type=float, default=None,
                   help="Resample all images to this µm/px (only for MIXED magnification).")
    p.add_argument("--no-morphotypes", action="store_true",
                   help="Skip KMeans morphotype clustering.")
    p.add_argument("--stats", action="store_true",
                   help="Print group comparison (mixed-effects if animal key, else Kruskal-Wallis).")
    p.add_argument("--plots", action="store_true",
                   help="Write QC/result figures to <out>/figures.")


_EXAMPLES = """\
examples:
  prion demo                              try it on built-in fake data (no setup)
  prion run --data ./images               the usual one-command run
  prion run --data ./images --animal-key animal_key.csv --stats --plots
  prion calibrate --data ./images         just step 1 (read the scale)
  prion phase1 --data ./images            just step 2 (needs a scale table)

New here? Run `prion demo` first to confirm everything works.
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="prion",
        description="CWD/prion PrP-burden quantification (Phase 0 calibrate + Phase 1).",
        epilog=_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--version", action="version", version=f"prion-ml-pipeline {__version__}")
    sub = p.add_subparsers(dest="command", metavar="<command>")

    # demo — the recommended starting point
    d = sub.add_parser("demo", help="Run the whole pipeline on built-in fake data (start here).")
    d.add_argument("--out", type=Path, default=None,
                   help="Where to put the demo data + results (default: ./prion_demo).")
    d.add_argument("--no-plots", action="store_true", help="Skip writing demo figures.")
    d.set_defaults(func=cmd_demo)

    # run — one command: calibrate + phase1
    r = sub.add_parser("run", help="One command: calibrate + Phase 1 on your images.")
    _add_common(r)
    _add_phase1_flags(r)
    r.set_defaults(func=cmd_run)

    # calibrate
    c = sub.add_parser("calibrate", help="Step 1 only: recover µm/px from TIFF metadata.")
    _add_common(c)
    c.add_argument("--out", type=Path, default=None,
                   help="Output scale table CSV (default: outputs_calib/scale_table.csv).")
    c.set_defaults(func=cmd_calibrate)

    # phase1
    f = sub.add_parser("phase1", help="Step 2 only: burden, morphometry, morphotypes.")
    _add_common(f)
    _add_phase1_flags(f)
    f.set_defaults(func=cmd_phase1)

    # sweep
    s = sub.add_parser("sweep", help="Help choose the DAB threshold (control vs treatment).")
    _add_common(s)
    s.add_argument("--scale-table", type=Path, default=None,
                   help="Per-image µm/px table (default: outputs_calib/scale_table.csv).")
    s.add_argument("--animal-key", type=Path, default=None,
                   help="CSV mapping image -> animal id (enables animal-level stats).")
    s.add_argument("--k", type=int, default=5, help="Images sampled per group (default 5).")
    s.add_argument("--out", type=Path, default=None, help="Optional CSV output for the sweep table.")
    s.add_argument("--plots", action="store_true", help="Also write a sweep figure next to --out.")
    s.set_defaults(func=cmd_sweep)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()  # bare `prion` -> show help, not an error
        return 0
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError) as exc:
        # Turn predictable input errors (e.g. a malformed --animal-key file)
        # into a clean message instead of a scary traceback.
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
