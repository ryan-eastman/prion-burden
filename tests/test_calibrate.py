import numpy as np
import tifffile

from prion_burden.calibrate import _to_um, build_scale_table, um_per_px_from_metadata


def test_to_um_units():
    assert _to_um(5.0, "um") == 5.0
    assert _to_um(5000.0, "nm") == 5.0
    assert _to_um(0.005, "mm") == 5.0
    assert _to_um(5e-6, "m") == 5e-6 * 1e6
    assert _to_um(5.0, None) == 5.0  # assume microns when unit absent


def test_um_per_px_from_resolution_tag(tmp_path):
    img = np.zeros((8, 8, 3), np.uint8)
    p = tmp_path / "img.tif"
    # 2000 px/cm -> 1e4 µm/cm / 2000 = 5.0 µm/px
    tifffile.imwrite(p, img, resolution=(2000, 2000), resolutionunit="CENTIMETER")
    upp = um_per_px_from_metadata(p)
    assert abs(upp - 5.0) < 1e-6


def test_um_per_px_nan_when_no_metadata(tmp_path):
    img = np.zeros((8, 8, 3), np.uint8)
    p = tmp_path / "bare.tif"
    tifffile.imwrite(p, img)  # no resolution tags
    assert np.isnan(um_per_px_from_metadata(p))


def test_build_scale_table_empty_dir_keeps_schema(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    mt = build_scale_table(empty, tmp_path / "out.csv")
    assert list(mt.columns) == ["image", "um_per_px"]  # no KeyError downstream
    assert len(mt) == 0


def test_build_scale_table_writes_csv(cohort_dir):
    data, _ = cohort_dir
    out = data.parent / "outputs_calib" / "scale_table.csv"
    mt = build_scale_table(data, out)
    assert out.exists()
    assert set(mt.columns) == {"image", "um_per_px"}
    assert len(mt) == 6
    assert np.allclose(mt["um_per_px"].values, 5.0)
