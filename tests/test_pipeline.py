"""End-to-end Phase 0 -> Phase 1 on the synthetic cohort."""

import pandas as pd

from prion_pipeline.analysis import group_comparison, threshold_sweep
from prion_pipeline.calibrate import build_scale_table
from prion_pipeline.config import Config
from prion_pipeline.discovery import discover_images, load_animal_key, load_scale_table
from prion_pipeline.pipeline import run_phase1


def _silent(_msg):  # swallow progress output in tests
    pass


def test_end_to_end(cohort_dir, tmp_path):
    data, key = cohort_dir
    scale_csv = tmp_path / "outputs_calib" / "scale_table.csv"
    out_dir = tmp_path / "outputs"

    build_scale_table(data, scale_csv)

    cfg = Config(
        data_dir=data,
        out_dir=out_dir,
        scale_table=scale_csv,
        animal_key=key,
    )
    result = run_phase1(cfg, do_morphotypes=True, progress=_silent)

    # CSVs written
    img_csv = out_dir / "per_image_summary.csv"
    obj_csv = out_dir / "per_object_features.csv"
    assert img_csv.exists() and obj_csv.exists()

    assert result.n_images == 6
    assert result.n_missing_scale == 0          # all had embedded 5 µm/px scale
    assert result.n_unknown_animal == 0          # animal key covered every image

    img_df = pd.read_csv(img_csv)
    assert {"pct_area_burden", "n_objects", "density_per_mm2"} <= set(img_df.columns)
    assert (img_df["um_per_px"] == 5.0).all()
    assert img_df["n_objects"].sum() > 0

    obj_df = pd.read_csv(obj_csv)
    assert "morphotype" in obj_df.columns
    assert "area_um2" in obj_df.columns


def test_run_phase1_without_scale_reports_pixels(cohort_dir, tmp_path):
    data, _ = cohort_dir
    cfg = Config(
        data_dir=data,
        out_dir=tmp_path / "out",
        scale_table=tmp_path / "missing.csv",  # no calibration
    )
    result = run_phase1(cfg, do_morphotypes=False, progress=_silent)
    assert result.n_missing_scale == result.n_images  # all fell back to pixels


def test_group_comparison_and_sweep(cohort_dir, tmp_path):
    data, key = cohort_dir
    scale_csv = tmp_path / "scale.csv"
    build_scale_table(data, scale_csv)
    cfg = Config(data_dir=data, out_dir=tmp_path / "o", scale_table=scale_csv, animal_key=key)
    result = run_phase1(cfg, progress=_silent)

    # Animal key supplied but species/condition are confounded here, so the
    # mixed model is rank-deficient and must degrade gracefully (not raise).
    rep = group_comparison(result.img_df, cfg)
    assert rep["method"] in ("mixedlm", "kruskal")
    assert isinstance(rep, dict)

    scale = load_scale_table(scale_csv)
    lookup = load_animal_key(key)
    paths = discover_images(data)
    pivot = threshold_sweep(paths, cfg, scale, lookup, k=2)
    assert isinstance(pivot, pd.DataFrame)
