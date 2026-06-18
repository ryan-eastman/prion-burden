import numpy as np

from prion_pipeline.config import Config
from prion_pipeline.segment import (
    _remove_small_holes,
    _remove_small_objects,
    dab_channel,
    object_features,
    segment_dab,
    tissue_mask,
)


def test_remove_small_objects_shim_removes_small_keeps_large():
    a = np.zeros((20, 60), int)
    a[2:4, 2:4] = 1     # 4-px object
    a[2:12, 20:40] = 2  # 200-px object
    out = _remove_small_objects(a, 50)
    kept = set(np.unique(out)) - {0}
    assert kept == {2}  # small removed, large kept


def test_remove_small_holes_shim_runs():
    mask = np.ones((10, 10), bool)
    mask[5, 5] = False  # 1-px hole
    out = _remove_small_holes(mask, 4)
    assert out[5, 5]  # hole filled


def test_tissue_mask_excludes_white_background():
    img = np.full((20, 20, 3), 255, np.uint8)  # pure white
    assert tissue_mask(img).sum() == 0


def test_segment_finds_dab_blobs(dab_image):
    cfg = Config()
    # empty scale -> upp is NaN -> no resample, no size filtering
    labels, pos, tis, area_frac, t = segment_dab(dab_image, np.nan, cfg)
    assert t == cfg.dab_threshold
    assert tis.sum() > 0
    assert labels.max() >= 1       # at least one deposit detected
    assert 0 < area_frac < 1


def test_object_features_columns(dab_image):
    cfg = Config()
    labels, *_ = segment_dab(dab_image, np.nan, cfg)
    df = object_features(labels, np.nan)
    assert len(df) >= 1
    for col in ("area_um2", "perimeter_um", "circularity", "aspect_ratio"):
        assert col in df.columns
    assert (df["circularity"] > 0).all()


def test_otsu_fallback_when_threshold_none(dab_image):
    cfg = Config(dab_threshold=None)
    labels, pos, tis, area_frac, t = segment_dab(dab_image, np.nan, cfg)
    assert not np.isnan(t)  # an Otsu threshold was computed
