"""Tests for the beginner entry points: synthetic data, `demo`, and `run`."""

from prion_burden.cli import build_parser, cmd_calibrate, cmd_demo, cmd_run, main
from prion_burden.demo import make_synthetic_cohort


def test_make_synthetic_cohort(tmp_path):
    data, key = make_synthetic_cohort(tmp_path / "root")
    imgs = sorted(data.glob("*.tif"))
    assert len(imgs) == 6
    assert key.exists()
    header = key.read_text().splitlines()[0]
    assert header == "image,animal,species,condition,region"


def test_cmd_demo_runs_end_to_end(tmp_path):
    args = build_parser().parse_args(
        ["demo", "--out", str(tmp_path / "demo"), "--no-plots"]
    )
    assert cmd_demo(args) == 0
    out = tmp_path / "demo" / "outputs"
    assert (out / "per_image_summary.csv").exists()
    assert (out / "per_object_features.csv").exists()
    assert (tmp_path / "demo" / "outputs_calib" / "scale_table.csv").exists()


def test_cmd_run_one_command(cohort_dir, tmp_path):
    data, key = cohort_dir
    out = tmp_path / "out"
    args = build_parser().parse_args(
        [
            "run",
            "--data", str(data),
            "--out", str(out),
            "--scale-table", str(tmp_path / "scale.csv"),
            "--animal-key", str(key),
        ]
    )
    assert cmd_run(args) == 0
    assert (out / "per_image_summary.csv").exists()
    assert (out / "per_object_features.csv").exists()
    assert (tmp_path / "scale.csv").exists()  # calibrate ran as step 1


def test_cmd_run_missing_data_dir_errors(tmp_path):
    args = build_parser().parse_args(["run", "--data", str(tmp_path / "nope")])
    assert cmd_run(args) == 2  # nonexistent folder -> clear failure


def test_cmd_run_empty_dir_errors(tmp_path):
    (tmp_path / "empty").mkdir()
    args = build_parser().parse_args(["run", "--data", str(tmp_path / "empty")])
    assert cmd_run(args) == 2  # exists but no images -> clean error, not KeyError


def test_cmd_calibrate_empty_dir_errors(tmp_path):
    (tmp_path / "empty").mkdir()
    args = build_parser().parse_args(["calibrate", "--data", str(tmp_path / "empty")])
    assert cmd_calibrate(args) == 2


def test_cmd_run_missing_animal_key_errors(cohort_dir, tmp_path):
    data, _ = cohort_dir
    args = build_parser().parse_args(
        ["run", "--data", str(data), "--out", str(tmp_path / "o"),
         "--animal-key", str(tmp_path / "nope.csv")]
    )
    assert cmd_run(args) == 2  # typo'd key path -> friendly error, not traceback


def test_main_malformed_animal_key_is_friendly(cohort_dir, tmp_path):
    data, _ = cohort_dir
    bad = tmp_path / "bad.csv"
    bad.write_text("foo,bar\n1,2\n")  # missing image/animal columns
    rc = main(["run", "--data", str(data), "--out", str(tmp_path / "o2"),
               "--scale-table", str(tmp_path / "s.csv"), "--animal-key", str(bad)])
    assert rc == 2  # ValueError caught at top level -> exit 2, no traceback


def test_run_scale_table_is_self_contained_under_out(cohort_dir, tmp_path):
    data, key = cohort_dir
    out = tmp_path / "results"
    args = build_parser().parse_args(
        ["run", "--data", str(data), "--out", str(out), "--animal-key", str(key)]
    )
    assert cmd_run(args) == 0
    # with no explicit --scale-table, the table lands under --out, not the cwd
    assert (out / "scale_table.csv").exists()
