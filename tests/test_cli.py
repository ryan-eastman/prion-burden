"""CLI wiring + config precedence (regression tests for the review findings)."""

from pathlib import Path

from prion_burden.cli import _build_config, build_parser, cmd_sweep


def _phase1_overrides(args):
    # Mirrors the override dict cmd_phase1 passes to _build_config.
    return dict(
        data_dir=args.data_dir,
        out_dir=args.out,
        scale_table=args.scale_table,
        animal_key=args.animal_key,
        dab_threshold=args.dab_threshold,
        min_object_um2=args.min_object_um2,
        target_um_per_px=args.target_um_per_px,
    )


def test_yaml_values_survive_unset_flags(tmp_path):
    """Precedence: a YAML value must NOT be clobbered by an unset CLI flag."""
    yaml = tmp_path / "c.yaml"
    yaml.write_text("out_dir: /yaml/out\nscale_table: /yaml/scale.csv\n")
    args = build_parser().parse_args(
        ["phase1", "--data", str(tmp_path), "--config", str(yaml)]
    )
    cfg = _build_config(args, **_phase1_overrides(args))
    assert cfg.out_dir == Path("/yaml/out")
    assert cfg.scale_table == Path("/yaml/scale.csv")


def test_explicit_flag_overrides_yaml(tmp_path):
    yaml = tmp_path / "c.yaml"
    yaml.write_text("out_dir: /yaml/out\n")
    args = build_parser().parse_args(
        ["phase1", "--data", str(tmp_path), "--config", str(yaml), "--out", "/cli/out"]
    )
    cfg = _build_config(args, **_phase1_overrides(args))
    assert cfg.out_dir == Path("/cli/out")  # explicit flag wins


def test_defaults_when_no_yaml_no_flag(tmp_path):
    args = build_parser().parse_args(["phase1", "--data", str(tmp_path)])
    cfg = _build_config(args, **_phase1_overrides(args))
    assert cfg.out_dir == Path("outputs")
    assert cfg.scale_table == Path("outputs_calib/scale_table.csv")


def test_calibrate_out_defaults_to_scale_table(tmp_path):
    args = build_parser().parse_args(["calibrate", "--data", str(tmp_path)])
    cfg = _build_config(args, data_dir=args.data_dir, scale_table=args.out)
    assert cfg.scale_table == Path("outputs_calib/scale_table.csv")


def test_sweep_animal_key_is_wired(tmp_path):
    key = tmp_path / "k.csv"
    args = build_parser().parse_args(
        ["sweep", "--data", str(tmp_path), "--animal-key", str(key)]
    )
    cfg = _build_config(
        args, data_dir=args.data_dir, scale_table=args.scale_table, animal_key=args.animal_key
    )
    assert cfg.animal_key == key  # no longer silently dropped


def test_sweep_empty_dir_returns_error_code(tmp_path):
    args = build_parser().parse_args(["sweep", "--data", str(tmp_path)])
    assert cmd_sweep(args) == 2  # missing/empty data -> clear failure, not exit 0
