import numpy as np
import tifffile

from prion_pipeline.config import Config
from prion_pipeline.discovery import (
    discover_images,
    get_um_per_px,
    load_animal_key,
    load_scale_table,
    parse_metadata,
)


def test_discover_dedup_by_filename(tmp_path):
    img = np.zeros((4, 4, 3), np.uint8)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    tifffile.imwrite(tmp_path / "a" / "dup.tif", img)
    tifffile.imwrite(tmp_path / "b" / "dup.tif", img)  # same name, different dir
    tifffile.imwrite(tmp_path / "a" / "unique.tif", img)
    found = discover_images(tmp_path)
    names = sorted(p.name for p in found)
    assert names == ["dup.tif", "unique.tif"]  # dup counted once


def test_parse_metadata():
    from pathlib import Path

    cfg = Config()
    m = parse_metadata(Path("GtDeer_treatment_cerebellum_4x_07.tif"), cfg, {})
    assert m["species"] == "deer"
    assert m["condition"] == "treatment"
    assert m["region"] == "cerebellum"
    assert m["magnification"] == "4x"
    assert m["image_id"] == "07"
    assert m["animal"] == "UNKNOWN"

    m2 = parse_metadata(Path("WT_control_midbrain_4x_03.tif"), cfg, {})
    assert m2["species"] == "wt" and m2["condition"] == "control" and m2["region"] == "midbrain"


def test_parse_metadata_uses_animal_key():
    from pathlib import Path

    cfg = Config()
    key = {"GtElk_treatment_cerebellum_4x_05": "J2009"}
    m = parse_metadata(Path("GtElk_treatment_cerebellum_4x_05.tif"), cfg, key)
    assert m["animal"] == "J2009"


def test_load_animal_key_keys_by_name_and_stem(tmp_path):
    p = tmp_path / "key.csv"
    p.write_text("image,animal\nGtDeer_treatment_cerebellum_4x_01.tif,J1\n")
    lk = load_animal_key(p)
    assert lk["GtDeer_treatment_cerebellum_4x_01.tif"] == "J1"
    assert lk["GtDeer_treatment_cerebellum_4x_01"] == "J1"  # by stem too


def test_load_scale_table_missing_is_empty(tmp_path):
    assert load_scale_table(tmp_path / "nope.csv") == {}


def test_get_um_per_px_nan_when_absent():
    from pathlib import Path

    assert np.isnan(get_um_per_px(Path("x.tif"), {}))
    assert get_um_per_px(Path("x.tif"), {"x.tif": 5.0}) == 5.0
