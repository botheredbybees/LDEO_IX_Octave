from pathlib import Path

import numpy as np
from scipy.io import loadmat, savemat

SADCP_CONVERT_SUFFIX = ".SADCP.mat"

_XY_VARS = ("xyt", "zc", "year_base")
_UV_VARS = ("uv",)


class SadcpConvertError(Exception):
    pass


def to_julian_day(year, month, day, hour=0.0):
    """Port of ldeo_ix/julian.m's day-number formula for a single date."""
    m = month + 9
    yr = year - 1
    if month > 2:
        m = month - 3
        yr = year
    c = yr // 100
    yr = yr - c * 100
    j = (146097 * c) // 4 + (1461 * yr) // 4 + (153 * m + 2) // 5 + day + 1721119
    return j + hour / 24


def convert(contour_dir: Path, data_mount_root: Path) -> str:
    contour_dir = Path(contour_dir)
    data_mount_root = Path(data_mount_root)
    xy_path = contour_dir / "contour_xy.mat"
    uv_path = contour_dir / "contour_uv.mat"

    if not xy_path.is_file():
        raise SadcpConvertError(f"{xy_path} not found")
    if not uv_path.is_file():
        raise SadcpConvertError(f"{uv_path} not found")

    try:
        xy = loadmat(str(xy_path))
    except Exception as exc:
        raise SadcpConvertError(f"could not read {xy_path}: {exc}") from exc
    try:
        uv = loadmat(str(uv_path))
    except Exception as exc:
        raise SadcpConvertError(f"could not read {uv_path}: {exc}") from exc

    missing_xy = [name for name in _XY_VARS if name not in xy]
    if missing_xy:
        raise SadcpConvertError(f"{xy_path} is missing expected variable(s): {', '.join(missing_xy)}")
    missing_uv = [name for name in _UV_VARS if name not in uv]
    if missing_uv:
        raise SadcpConvertError(f"{uv_path} is missing expected variable(s): {', '.join(missing_uv)}")

    xyt = np.asarray(xy["xyt"], dtype=float)
    z_sadcp = np.asarray(xy["zc"], dtype=float).reshape(-1, 1)
    year_base = float(np.asarray(xy["year_base"]).squeeze())
    uv_arr = np.asarray(uv["uv"], dtype=float)

    if uv_arr.ndim != 2 or uv_arr.shape[1] != 2 * xyt.shape[1]:
        raise SadcpConvertError(
            f"{uv_path}'s 'uv' shape {uv_arr.shape} is not compatible with "
            f"{xy_path}'s time dimension ({xyt.shape[1]})"
        )

    lon = xyt[0, :]
    lat = xyt[1, :]
    dday = xyt[2, :]

    valid = np.isfinite(lon) & np.isfinite(lat) & np.isfinite(dday)
    if not np.any(valid):
        raise SadcpConvertError(f"no valid SADCP time/position entries found in {contour_dir}")

    lon = lon[valid]
    lat = lat[valid]
    dday = dday[valid]
    u_sadcp = uv_arr[:, 0::2][:, valid]
    v_sadcp = uv_arr[:, 1::2][:, valid]

    lon_sadcp = ((lon + 180.0) % 360.0) - 180.0
    lat_sadcp = lat
    tim_sadcp = to_julian_day(year_base, 1, 1, 0.0) + dday

    output_dir = data_mount_root / "sadcp_convert"
    output_name = f"{contour_dir.parent.name}{SADCP_CONVERT_SUFFIX}"
    output_path = output_dir / output_name
    output_dir.mkdir(parents=True, exist_ok=True)

    savemat(str(output_path), {
        "tim_sadcp": tim_sadcp.reshape(-1, 1),
        "lat_sadcp": lat_sadcp.reshape(-1, 1),
        "lon_sadcp": lon_sadcp.reshape(-1, 1),
        "u_sadcp": u_sadcp,
        "v_sadcp": v_sadcp,
        "z_sadcp": z_sadcp,
    })

    return f"sadcp_convert/{output_name}"
