from pathlib import Path

import numpy as np
import pytest
from scipy.io import loadmat, savemat

from webapp import sadcp_convert


def _write_contour_fixture(contour_dir, lon, lat, dday, zc, u, v, year_base=2024):
    contour_dir.mkdir(parents=True, exist_ok=True)
    xyt = np.vstack([lon, lat, dday])
    savemat(str(contour_dir / "contour_xy.mat"), {
        "xyt": xyt, "zc": zc, "year_base": float(year_base),
    })
    n_depth, n_time = u.shape
    uv = np.empty((n_depth, n_time * 2))
    uv[:, 0::2] = u
    uv[:, 1::2] = v
    savemat(str(contour_dir / "contour_uv.mat"), {"uv": uv})


def test_to_julian_day_matches_known_reference():
    # ldeo_ix/julian.m's own docstring: JD 2440000 began 0000 hours, May 23, 1968.
    assert sadcp_convert.to_julian_day(1968, 5, 23, 0.0) == 2440000


def test_convert_writes_expected_variables(tmp_path):
    contour_dir = tmp_path / "codas" / "os150nb" / "contour"
    lon = np.array([148.5, 148.6, 148.7])
    lat = np.array([-42.5, -42.55, -42.6])
    dday = np.array([168.1, 168.2, 168.3])
    zc = np.array([[10.0], [20.0]])
    u = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
    v = np.array([[-0.1, -0.2, -0.3], [-0.4, -0.5, -0.6]])
    _write_contour_fixture(contour_dir, lon, lat, dday, zc, u, v, year_base=2024)
    data_mount = tmp_path / "data"
    data_mount.mkdir()

    result = sadcp_convert.convert(contour_dir, data_mount)

    assert result == "sadcp_convert/os150nb.SADCP.mat"
    written = data_mount / "sadcp_convert" / "os150nb.SADCP.mat"
    assert written.is_file()

    out = loadmat(str(written))
    expected_tim = sadcp_convert.to_julian_day(2024, 1, 1, 0.0) + dday
    np.testing.assert_allclose(out["tim_sadcp"].ravel(), expected_tim)
    np.testing.assert_allclose(out["lat_sadcp"].ravel(), lat)
    np.testing.assert_allclose(out["lon_sadcp"].ravel(), lon)
    np.testing.assert_allclose(out["z_sadcp"].ravel(), zc.ravel())
    np.testing.assert_allclose(out["u_sadcp"], u)
    np.testing.assert_allclose(out["v_sadcp"], v)


def test_convert_normalizes_longitude_over_180(tmp_path):
    contour_dir = tmp_path / "contour"
    lon = np.array([200.0, 210.0])  # equivalent to -160, -150
    lat = np.array([-42.0, -42.1])
    dday = np.array([100.0, 100.1])
    zc = np.array([[10.0]])
    u = np.array([[0.1, 0.2]])
    v = np.array([[0.3, 0.4]])
    _write_contour_fixture(contour_dir, lon, lat, dday, zc, u, v)
    data_mount = tmp_path / "data"
    data_mount.mkdir()

    result = sadcp_convert.convert(contour_dir, data_mount)
    out = loadmat(str(data_mount / result))

    np.testing.assert_allclose(out["lon_sadcp"].ravel(), [-160.0, -150.0])


def test_convert_drops_nan_entries(tmp_path):
    contour_dir = tmp_path / "contour"
    lon = np.array([148.5, np.nan, 148.7])
    lat = np.array([-42.5, -42.55, -42.6])
    dday = np.array([168.1, 168.2, 168.3])
    zc = np.array([[10.0]])
    u = np.array([[1.0, 2.0, 3.0]])
    v = np.array([[4.0, 5.0, 6.0]])
    _write_contour_fixture(contour_dir, lon, lat, dday, zc, u, v)
    data_mount = tmp_path / "data"
    data_mount.mkdir()

    result = sadcp_convert.convert(contour_dir, data_mount)
    out = loadmat(str(data_mount / result))

    assert out["lon_sadcp"].ravel().shape == (2,)
    np.testing.assert_allclose(out["lon_sadcp"].ravel(), [148.5, 148.7])
    np.testing.assert_allclose(out["u_sadcp"].ravel(), [1.0, 3.0])


def test_convert_raises_for_missing_contour_files(tmp_path):
    contour_dir = tmp_path / "contour"
    contour_dir.mkdir()
    data_mount = tmp_path / "data"
    data_mount.mkdir()

    with pytest.raises(sadcp_convert.SadcpConvertError):
        sadcp_convert.convert(contour_dir, data_mount)


def test_convert_raises_for_missing_variables(tmp_path):
    contour_dir = tmp_path / "contour"
    contour_dir.mkdir()
    savemat(str(contour_dir / "contour_xy.mat"), {"something_else": 1})
    savemat(str(contour_dir / "contour_uv.mat"), {"uv": np.zeros((2, 2))})
    data_mount = tmp_path / "data"
    data_mount.mkdir()

    with pytest.raises(sadcp_convert.SadcpConvertError):
        sadcp_convert.convert(contour_dir, data_mount)


def test_convert_raises_for_incompatible_uv_shape(tmp_path):
    contour_dir = tmp_path / "contour"
    contour_dir.mkdir()
    savemat(str(contour_dir / "contour_xy.mat"), {
        "xyt": np.vstack([[148.5, 148.6], [-42.5, -42.6], [100.0, 100.1]]),
        "zc": np.array([[10.0]]),
        "year_base": 2024.0,
    })
    savemat(str(contour_dir / "contour_uv.mat"), {"uv": np.zeros((1, 3))})  # odd, and wrong count
    data_mount = tmp_path / "data"
    data_mount.mkdir()

    with pytest.raises(sadcp_convert.SadcpConvertError):
        sadcp_convert.convert(contour_dir, data_mount)


def test_convert_raises_for_too_few_xyt_rows(tmp_path):
    contour_dir = tmp_path / "contour"
    contour_dir.mkdir()
    savemat(str(contour_dir / "contour_xy.mat"), {
        "xyt": np.vstack([[148.5, 148.6], [-42.5, -42.6]]),  # only 2 rows: lon, lat -- no dday
        "zc": np.array([[10.0]]),
        "year_base": 2024.0,
    })
    savemat(str(contour_dir / "contour_uv.mat"), {"uv": np.zeros((1, 4))})
    data_mount = tmp_path / "data"
    data_mount.mkdir()

    with pytest.raises(sadcp_convert.SadcpConvertError):
        sadcp_convert.convert(contour_dir, data_mount)


def test_convert_raises_for_non_numeric_year_base(tmp_path):
    contour_dir = tmp_path / "contour"
    contour_dir.mkdir()
    savemat(str(contour_dir / "contour_xy.mat"), {
        "xyt": np.vstack([[148.5, 148.6], [-42.5, -42.6], [100.0, 100.1]]),
        "zc": np.array([[10.0]]),
        "year_base": "not-a-number",
    })
    savemat(str(contour_dir / "contour_uv.mat"), {"uv": np.zeros((1, 4))})
    data_mount = tmp_path / "data"
    data_mount.mkdir()

    with pytest.raises(sadcp_convert.SadcpConvertError):
        sadcp_convert.convert(contour_dir, data_mount)


def test_convert_raises_when_all_entries_invalid(tmp_path):
    contour_dir = tmp_path / "contour"
    lon = np.array([np.nan, np.nan])
    lat = np.array([-42.0, -42.1])
    dday = np.array([100.0, 100.1])
    zc = np.array([[10.0]])
    u = np.array([[1.0, 2.0]])
    v = np.array([[3.0, 4.0]])
    _write_contour_fixture(contour_dir, lon, lat, dday, zc, u, v)
    data_mount = tmp_path / "data"
    data_mount.mkdir()

    with pytest.raises(sadcp_convert.SadcpConvertError):
        sadcp_convert.convert(contour_dir, data_mount)
