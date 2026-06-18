import math
from pathlib import Path

import pytest

from prion_pipeline.config import Config


def test_defaults_reproduce_notebook():
    cfg = Config()
    assert cfg.dab_threshold == 0.05
    assert cfg.min_object_um2 == 50.0
    assert cfg.min_peak_dist == 3
    assert cfg.target_um_per_px is None
    assert cfg.regions == ["cerebellum", "hippocampus", "midbrain", "septum"]


def test_merge_overrides_ignores_none():
    cfg = Config(dab_threshold=0.05)
    merged = cfg.merge_overrides(dab_threshold=None, min_object_um2=20.0)
    assert merged.dab_threshold == 0.05  # None did not clobber
    assert merged.min_object_um2 == 20.0


def test_unknown_key_rejected():
    with pytest.raises(ValueError):
        Config.from_dict({"not_a_real_key": 1})


def test_path_coercion():
    cfg = Config(data_dir="/tmp/x", out_dir="out")
    assert isinstance(cfg.data_dir, Path)
    assert isinstance(cfg.out_dir, Path)


def test_target_um_per_px_none_to_nan():
    assert math.isnan(Config().effective_target_um_per_px())
    assert Config(target_um_per_px="none").target_um_per_px is None
    assert Config(target_um_per_px="0.5").target_um_per_px == 0.5


def test_from_yaml(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("dab_threshold: 0.08\nregions: [cerebellum]\ntarget_um_per_px: null\n")
    cfg = Config.from_yaml(p)
    assert cfg.dab_threshold == 0.08
    assert cfg.regions == ["cerebellum"]
    assert cfg.target_um_per_px is None
