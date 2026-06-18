"""Command-line interface: ``prion calibrate | phase1 | sweep``.

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


# --- calibrate -------------------------------------------------------------
def cmd_calibrate(args: argparse.Namespace) -> int:
    cfg = _build_config(
        args,
        data_dir=args.data_dir,
        scale_table=args.out,
    )
    if cfg.data_dir is None:
        print("error: --data is required", file=sys.stderr)
        return 2
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
    if cfg.data_dir is None:
        print("error: --data is required", file=sys.stderr)
        return 2

    from .pipeline import run_phase1

    result = run_phase1(cfg, do_morphotypes=not args.no_morphotypes)

    if args.stats and len(result.img_df):
        from .analysis import group_comparison

        rep = group_comparison(result.img_df, cfg)
        print("\n=== Group comparison ===")
        if rep["method"] == "mixedlm":
            print(f"Mixed-effects model (animal random effect), "
                  f"{rep['n_animals']} animals:\n{rep['summary']}")
        else:
            print(f"{rep['note']}")
            for reg, r in rep.get("per_region", {}).items():
                print(f"  {reg:12s} Kruskal-Wallis H={r['H']:.2f} p={r['p']:.3g} groups={r['groups']}")

    if args.plots and len(result.img_df):
        _write_plots(cfg, result)

    return 0


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


# --- sweep -----------------------------------------------------------------
def cmd_sweep(args: argparse.Namespace) -> int:
    cfg = _build_config(
        args,
        data_dir=args.data_dir,
        scale_table=args.scale_table,
        animal_key=args.animal_key,
    )
    if cfg.data_dir is None:
        print("error: --data is required", file=sys.stderr)
        return 2

    from .analysis import threshold_sweep
    from .discovery import discover_images, load_animal_key, load_scale_table

    image_paths = discover_images(cfg.data_dir)
    if not image_paths:
        print(f"No images found under {cfg.data_dir} — check --data.", file=sys.stderr)
        return 2
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
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="prion",
        description="CWD/prion PrP-burden quantification (Phase 0 calibrate + Phase 1).",
    )
    p.add_argument("--version", action="version", version=f"prion-ml-pipeline {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    # calibrate
    c = sub.add_parser("calibrate", help="Phase 0: recover µm/px from TIFF metadata.")
    _add_common(c)
    c.add_argument("--out", type=Path, default=None,
                   help="Output scale table CSV (default: outputs_calib/scale_table.csv).")
    c.set_defaults(func=cmd_calibrate)

    # phase1
    f = sub.add_parser("phase1", help="Phase 1: burden, morphometry, morphotypes.")
    _add_common(f)
    f.add_argument("--out", dest="out", type=Path, default=None,
                   help="Output directory for CSVs/figures (default: outputs).")
    f.add_argument("--scale-table", type=Path, default=None,
                   help="Per-image µm/px table from `prion calibrate` (default: outputs_calib/scale_table.csv).")
    f.add_argument("--animal-key", type=Path, default=None,
                   help="CSV mapping image -> animal id (enables animal-level stats).")
    f.add_argument("--dab-threshold", type=float, default=None,
                   help="Fixed DAB optical-density cutoff (default 0.05; comparable across images).")
    f.add_argument("--min-object-um2", type=float, default=None,
                   help="Minimum object area in µm^2 (default 50).")
    f.add_argument("--target-um-per-px", type=float, default=None,
                   help="Resample all images to this µm/px (only for MIXED magnification).")
    f.add_argument("--no-morphotypes", action="store_true",
                   help="Skip KMeans morphotype clustering.")
    f.add_argument("--stats", action="store_true",
                   help="Print group comparison (mixed-effects if animal key, else Kruskal-Wallis).")
    f.add_argument("--plots", action="store_true",
                   help="Write QC/result figures to <out>/figures.")
    f.set_defaults(func=cmd_phase1)

    # sweep
    s = sub.add_parser("sweep", help="Calibrate the DAB threshold (control vs treatment).")
    _add_common(s)
    s.add_argument("--scale-table", type=Path, default=None,
                   help="Per-image µm/px table (default: outputs_calib/scale_table.csv).")
    s.add_argument("--animal-key", type=Path, default=None)
    s.add_argument("--k", type=int, default=5, help="Images sampled per group (default 5).")
    s.add_argument("--out", type=Path, default=None, help="Optional CSV output for the sweep table.")
    s.add_argument("--plots", action="store_true", help="Also write a sweep figure next to --out.")
    s.set_defaults(func=cmd_sweep)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
