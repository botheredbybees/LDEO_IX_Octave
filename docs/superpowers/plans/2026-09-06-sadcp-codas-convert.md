# SADCP Conversion from CODAS Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the cruise/cast intake webapp convert CODAS's native SADCP output (`contour_xy.mat`/`contour_uv.mat`) into the `.mat` file `ldeo_ix/loadsadcp.m` expects, via a browser button, instead of requiring a manual MATLAB/Octave session.

**Architecture:** A pure-logic Python port of `ldeo_ix/mkSADCP.m` (`webapp/sadcp_convert.py`), wired into the webapp the same way `webapp/quick_convert.py` is: a new `codas` mount, a new stateless POST endpoint, and a browse-and-run UI section next to the SADCP field. The conversion covers a whole voyage in one call — no per-cast time-window logic, since `loadsadcp.m` already does that windowing at runtime.

**Tech Stack:** Python (FastAPI, `scipy.io.loadmat`/`savemat` — already a dependency, no new packages), vanilla JS/HTML (no build step, matching the rest of `webapp/`).

**Spec:** `docs/superpowers/specs/2026-09-06-sadcp-codas-extract-design.md`

## Global Constraints

- No new dependencies — `scipy` is already required (`webapp/requirements.txt`); this only uses new entry points (`loadmat`/`savemat`) from it.
- Output file suffix is `.SADCP.mat` exactly (constant `SADCP_CONVERT_SUFFIX` in `webapp/sadcp_convert.py`), written to `sadcp_convert/<instrument-dir-name>.SADCP.mat` under the `data` mount.
- New mount: key `"codas"`, env var `LDEO_CODAS_DIR`, default container path `/codas_data`.
- New endpoint is `POST /api/sadcp/convert` — deliberately not under `/api/quick-convert/`, since this performs no calibration shortcut the way the CTD hex fallback does.
- No per-cast time-window or buffer parameter anywhere in this feature. `loadsadcp.m`'s own `p.sadcp_dtok` runtime windowing is what narrows a converted file down per cast.
- The "Convert CODAS SADCP data" UI is hidden unless the `codas` mount is present (`GET /api/mounts` includes `"codas"`).

---

### Task 1: `webapp/sadcp_convert.py` — port `mkSADCP.m`

**Files:**
- Create: `webapp/sadcp_convert.py`
- Test: `webapp/tests/test_sadcp_convert.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `sadcp_convert.SadcpConvertError` (exception class); `sadcp_convert.to_julian_day(year: float, month: int, day: int, hour: float = 0.0) -> float`; `sadcp_convert.convert(contour_dir: Path, data_mount_root: Path) -> str` (returns a path relative to `data_mount_root`, e.g. `"sadcp_convert/os150nb.SADCP.mat"`). `sadcp_convert.SADCP_CONVERT_SUFFIX = ".SADCP.mat"`. Tasks 2 and 3 import all of these.

- [ ] **Step 1: Write the failing tests**

Create `webapp/tests/test_sadcp_convert.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest webapp/tests/test_sadcp_convert.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'webapp.sadcp_convert'` (or `ImportError`).

- [ ] **Step 3: Write the implementation**

Create `webapp/sadcp_convert.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest webapp/tests/test_sadcp_convert.py -v`
Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add webapp/sadcp_convert.py webapp/tests/test_sadcp_convert.py
git commit -m "$(cat <<'EOF'
feat: add sadcp_convert.py, a Python port of ldeo_ix/mkSADCP.m

Converts CODAS's native contour_xy.mat/contour_uv.mat pair into the
.mat format loadsadcp.m expects -- same transform, same inputs, same
output variables as the MATLAB tool already shipped in this repo.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EsPQKR9bs6vz4Rt8bSMEw
EOF
)"
```

---

### Task 2: `codas` mount + `POST /api/sadcp/convert`

**Files:**
- Modify: `webapp/config.py`
- Modify: `webapp/main.py`
- Test: `webapp/tests/test_api_sadcp_convert.py` (create)

**Interfaces:**
- Consumes: `sadcp_convert.SadcpConvertError`, `sadcp_convert.convert(contour_dir, data_mount_root) -> str` (Task 1). `paths.resolve_within(mount_root: Path, relative: str) -> Path` (existing, `webapp/paths.py`), raising `paths.PathOutsideMountError`.
- Produces: `config.MOUNTS["codas"]`; route `POST /api/sadcp/convert` accepting `{"contour_dir": str}`, returning `{"sadcp_path": str}` on success, `400`/`404` with a `detail` string on failure. Task 4's frontend calls this route by name and reads `body.sadcp_path`.

- [ ] **Step 1: Write the failing tests**

Create `webapp/tests/test_api_sadcp_convert.py`:

```python
from fastapi.testclient import TestClient

from webapp import config, main, sadcp_convert


def test_sadcp_convert_success(tmp_path, monkeypatch):
    codas_mount = tmp_path / "codas"
    data_mount = tmp_path / "data"
    contour_dir = codas_mount / "os150nb" / "contour"
    contour_dir.mkdir(parents=True)
    data_mount.mkdir()
    monkeypatch.setitem(config.MOUNTS, "codas", codas_mount)
    monkeypatch.setitem(config.MOUNTS, "data", data_mount)

    def _fake_convert(contour_dir_arg, data_mount_root):
        assert contour_dir_arg == contour_dir
        assert data_mount_root == data_mount
        return "sadcp_convert/os150nb.SADCP.mat"

    monkeypatch.setattr(sadcp_convert, "convert", _fake_convert)

    client = TestClient(main.app)
    response = client.post("/api/sadcp/convert", json={"contour_dir": "os150nb/contour"})

    assert response.status_code == 200
    assert response.json() == {"sadcp_path": "sadcp_convert/os150nb.SADCP.mat"}


def test_sadcp_convert_rejects_path_traversal(tmp_path, monkeypatch):
    codas_mount = tmp_path / "codas"
    data_mount = tmp_path / "data"
    codas_mount.mkdir()
    data_mount.mkdir()
    monkeypatch.setitem(config.MOUNTS, "codas", codas_mount)
    monkeypatch.setitem(config.MOUNTS, "data", data_mount)

    client = TestClient(main.app)
    response = client.post("/api/sadcp/convert", json={"contour_dir": "../../etc"})

    assert response.status_code == 400


def test_sadcp_convert_surfaces_conversion_error(tmp_path, monkeypatch):
    codas_mount = tmp_path / "codas"
    data_mount = tmp_path / "data"
    codas_mount.mkdir()
    data_mount.mkdir()
    monkeypatch.setitem(config.MOUNTS, "codas", codas_mount)
    monkeypatch.setitem(config.MOUNTS, "data", data_mount)

    def _fake_convert(contour_dir_arg, data_mount_root):
        raise sadcp_convert.SadcpConvertError("contour_xy.mat not found")

    monkeypatch.setattr(sadcp_convert, "convert", _fake_convert)

    client = TestClient(main.app)
    response = client.post("/api/sadcp/convert", json={"contour_dir": "os150nb/contour"})

    assert response.status_code == 400
    assert "contour_xy.mat not found" in response.json()["detail"]


def test_sadcp_convert_rejects_missing_codas_mount():
    client = TestClient(main.app)
    response = client.post("/api/sadcp/convert", json={"contour_dir": "os150nb/contour"})

    assert response.status_code == 404


def test_mounts_endpoint_includes_codas_when_configured(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "codas", tmp_path)

    client = TestClient(main.app)
    response = client.get("/api/mounts")

    assert "codas" in response.json()["mounts"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest webapp/tests/test_api_sadcp_convert.py -v`
Expected: FAIL — `test_sadcp_convert_rejects_missing_codas_mount` gets a 404 anyway (no route yet is also a 404, so this one may pass already), but the other tests FAIL with 404 "Not Found" from FastAPI (no such route) instead of the expected behavior.

- [ ] **Step 3: Add the `codas` mount**

In `webapp/config.py`, add one line to `MOUNTS`:

```python
MOUNTS: dict[str, Path] = {
    "data": Path(os.environ.get("LDEO_DATA_DIR", "/data")),
    "ladcp": Path(os.environ.get("LDEO_LADCP_DIR", "/ladcp_data")),
    "ctd": Path(os.environ.get("LDEO_CTD_DIR", "/ctd_data")),
    "sadcp": Path(os.environ.get("LDEO_SADCP_DIR", "/sadcp_data")),
    "nav": Path(os.environ.get("LDEO_NAV_DIR", "/navigation_data")),
    "codas": Path(os.environ.get("LDEO_CODAS_DIR", "/codas_data")),
}
```

- [ ] **Step 4: Add the route**

In `webapp/main.py`, add `sadcp_convert` to the import line:

```python
from webapp import api, config, delimited_parser, field_role_suggest, file_browser, ladcp_scan, paths, quick_convert, sadcp_convert
```

Then add, directly after the existing `quick_convert_ctd` route:

```python
class SadcpConvertRequest(BaseModel):
    contour_dir: str


@app.post("/api/sadcp/convert")
def sadcp_convert_route(body: SadcpConvertRequest):
    codas_mount = config.MOUNTS.get("codas")
    data_mount = config.MOUNTS.get("data")
    if codas_mount is None or not codas_mount.is_dir():
        raise HTTPException(status_code=404, detail="codas mount not available")
    if data_mount is None or not data_mount.is_dir():
        raise HTTPException(status_code=404, detail="data mount not available")

    try:
        resolved_dir = paths.resolve_within(codas_mount, body.contour_dir)
    except paths.PathOutsideMountError:
        raise HTTPException(status_code=400, detail="path is outside the allowed directory")

    try:
        sadcp_path = sadcp_convert.convert(resolved_dir, data_mount)
    except sadcp_convert.SadcpConvertError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"sadcp_path": sadcp_path}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest webapp/tests/test_api_sadcp_convert.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 6: Run the full test suite to check for regressions**

Run: `python -m pytest webapp/tests -v`
Expected: all tests PASS (existing tests unaffected — this task only adds a mount entry and a new route).

- [ ] **Step 7: Commit**

```bash
git add webapp/config.py webapp/main.py webapp/tests/test_api_sadcp_convert.py
git commit -m "$(cat <<'EOF'
feat: add codas mount and POST /api/sadcp/convert endpoint

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EsPQKR9bs6vz4Rt8bSMEw
EOF
)"
```

---

### Task 3: Validation — check converted SADCP files against the `data` mount

**Files:**
- Modify: `webapp/validation.py`
- Modify: `webapp/tests/test_validation.py`

**Interfaces:**
- Consumes: `sadcp_convert.SADCP_CONVERT_SUFFIX` (Task 1).
- Produces: no new public interface — this only changes `validate_session`'s internal file-existence check for the `sadcp` field, mirroring the existing `ctd`/`quick_convert.QUICKCONVERT_SUFFIX` special case already in `validate_session`.

- [ ] **Step 1: Write the failing tests**

Add to `webapp/tests/test_validation.py`:

```python
def test_sadcp_converted_file_checked_against_data_mount_not_sadcp_mount(tmp_path, monkeypatch):
    data_mount = tmp_path / "data"
    sadcp_mount = tmp_path / "sadcp"
    ladcp_mount = tmp_path / "ladcp"
    data_mount.mkdir()
    sadcp_mount.mkdir()
    ladcp_mount.mkdir()
    sadcp_convert_dir = data_mount / "sadcp_convert"
    sadcp_convert_dir.mkdir()
    (sadcp_convert_dir / "os150nb.SADCP.mat").write_text("fake mat")
    (ladcp_mount / "003DL000.000").write_text("")
    (ladcp_mount / "003UL000.000").write_text("")
    monkeypatch.setitem(config.MOUNTS, "data", data_mount)
    monkeypatch.setitem(config.MOUNTS, "sadcp", sadcp_mount)
    monkeypatch.setitem(config.MOUNTS, "ladcp", ladcp_mount)

    session = CruiseSession(casts=[_valid_cast(sadcp="sadcp_convert/os150nb.SADCP.mat")])

    result = validation.validate_session(session)

    assert result.warnings == {}


def test_missing_sadcp_converted_file_warns_about_data_mount_not_sadcp_mount(tmp_path, monkeypatch):
    data_mount = tmp_path / "data"
    sadcp_mount = tmp_path / "sadcp"
    ladcp_mount = tmp_path / "ladcp"
    data_mount.mkdir()
    sadcp_mount.mkdir()
    ladcp_mount.mkdir()
    (ladcp_mount / "003DL000.000").write_text("")
    (ladcp_mount / "003UL000.000").write_text("")
    monkeypatch.setitem(config.MOUNTS, "data", data_mount)
    monkeypatch.setitem(config.MOUNTS, "sadcp", sadcp_mount)
    monkeypatch.setitem(config.MOUNTS, "ladcp", ladcp_mount)

    cast = _valid_cast(sadcp="sadcp_convert/os150nb.SADCP.mat")
    session = CruiseSession(casts=[cast])

    result = validation.validate_session(session)

    assert result.is_valid is True
    assert "sadcp_convert/os150nb.SADCP.mat not found under data mount" in result.warnings[cast.id]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest webapp/tests/test_validation.py -v`
Expected: the two new tests FAIL — `test_sadcp_converted_file_checked_against_data_mount_not_sadcp_mount` reports a warning (`sadcp_convert/os150nb.SADCP.mat not found under sadcp mount`) because it's currently checked against the `sadcp` mount instead of `data`.

- [ ] **Step 3: Update `validate_session`**

In `webapp/validation.py`, add the import and the new branch:

```python
from webapp import config, paths, quick_convert, sadcp_convert
```

Change the mount-selection block inside the `_FILE_FIELDS` loop from:

```python
            if field_name == "ctd" and relative.endswith(quick_convert.QUICKCONVERT_SUFFIX):
                mount_root = config.MOUNTS.get("data")
                checked_mount_name = "data"
            else:
                mount_root = config.MOUNTS.get(mount_name)
                checked_mount_name = mount_name
```

to:

```python
            if field_name == "ctd" and relative.endswith(quick_convert.QUICKCONVERT_SUFFIX):
                mount_root = config.MOUNTS.get("data")
                checked_mount_name = "data"
            elif field_name == "sadcp" and relative.endswith(sadcp_convert.SADCP_CONVERT_SUFFIX):
                mount_root = config.MOUNTS.get("data")
                checked_mount_name = "data"
            else:
                mount_root = config.MOUNTS.get(mount_name)
                checked_mount_name = mount_name
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest webapp/tests/test_validation.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `python -m pytest webapp/tests -v`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add webapp/validation.py webapp/tests/test_validation.py
git commit -m "$(cat <<'EOF'
fix: check converted SADCP files against the data mount, not sadcp

Mirrors the existing special case for quick-converted CTD files --
sadcp_convert.py writes into the data mount, so a converted SADCP path
would otherwise fail validation's file-existence check against the
(unrelated) sadcp mount.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EsPQKR9bs6vz4Rt8bSMEw
EOF
)"
```

---

### Task 4: UI — SADCP field and "Convert CODAS SADCP data"

**Files:**
- Modify: `webapp/templates/index.html`
- Modify: `webapp/static/app.js`

**Interfaces:**
- Consumes: `POST /api/sadcp/convert` (Task 2, body `{contour_dir}`, response `{sadcp_path}`); `GET /api/mounts` (existing, response `{mounts: string[]}`); existing `api()`, `openModal()`, `closeModal()`, `updateSaveStateFromForm()` helpers already in `app.js`.
- Produces: nothing consumed by a later task — this is the last task.

There is currently **no SADCP field in the form at all** (checked: `grep -i sadcp webapp/templates/index.html webapp/static/app.js` returns nothing), even though `CastEntry.sadcp` and the `sadcp` mount already exist server-side. This task adds both the plain field and the conversion UI in one pass.

- [ ] **Step 1: Add the SADCP fieldset to `index.html`**

In `webapp/templates/index.html`, insert this new `<fieldset>` between the closing `</fieldset>` of the Nav section and the opening `<fieldset class="card">` of "Position / time / bottom-tracking" (i.e. right after the line `    </fieldset>` that closes Nav, currently followed by a blank line and then `    <fieldset class="card">` / `      <legend>Position / time / bottom-tracking</legend>`):

```html
    <fieldset class="card">
      <legend>SADCP</legend>
      <label>File
        <input name="sadcp" id="sadcp-path">
        <button type="button" id="browse-sadcp" class="btn btn-secondary">Browse</button>
      </label>

      <details id="sadcp-convert-section" hidden>
        <summary>Convert CODAS SADCP data</summary>
        <label>CODAS contour directory
          <input id="codas-contour-path" readonly>
          <button type="button" id="browse-codas-contour" class="btn btn-secondary">Browse</button>
        </label>
        <button type="button" id="run-sadcp-convert" class="btn btn-secondary">Convert CODAS SADCP data</button>
        <div id="sadcp-convert-result"></div>
      </details>
    </fieldset>
```

- [ ] **Step 2: Add `selectDirs` support to the browser widget in `app.js`**

The existing `renderBrowserPanel`/`initBrowser` functions only ever let you pick a *file* — clicking a directory always navigates into it. Picking a CODAS `contour/` directory needs a way to select the directory you're currently viewing. Replace the current `renderBrowserPanel` and `initBrowser` functions with versions that accept an optional `options.selectDirs` flag, defaulting to `false` so every existing call site (`browse-ctd`, `browse-nav`, `browse-ladcpdo`, `browse-ladcpup`, `browse-quickconvert-hex`, `browse-quickconvert-xmlcon`) behaves exactly as before:

```javascript
async function renderBrowserPanel(container, mount, targetInputId, relativePath, options = {}) {
  const { selectDirs = false } = options;
  container.dataset.currentPath = relativePath;
  container.innerHTML = "";

  const pathLine = document.createElement("div");
  pathLine.className = "browser-path";
  pathLine.textContent = `${mount}:/${relativePath}`;
  container.appendChild(pathLine);

  if (selectDirs) {
    const useButton = document.createElement("button");
    useButton.type = "button";
    useButton.className = "btn btn-secondary";
    useButton.textContent = "Use this directory";
    useButton.addEventListener("click", () => {
      document.getElementById(targetInputId).value = relativePath;
      updateSaveStateFromForm();
      closeModal();
    });
    container.appendChild(useButton);
  }

  let data;
  try {
    data = await api(`/api/browse/${mount}?path=${encodeURIComponent(relativePath)}`);
  } catch (e) {
    const err = document.createElement("div");
    err.className = "browser-error";
    err.textContent = (e.body && e.body.detail) || `could not browse ${mount}`;
    container.appendChild(err);
    return;
  }

  if (relativePath) {
    const up = document.createElement("div");
    up.className = "browser-entry is-dir";
    up.textContent = ".. (up)";
    up.addEventListener("click", () => {
      const parent = relativePath.split("/").slice(0, -1).join("/");
      renderBrowserPanel(container, mount, targetInputId, parent, options);
    });
    container.appendChild(up);
  }

  for (const entry of data.entries) {
    const row = document.createElement("div");
    row.className = entry.is_dir ? "browser-entry is-dir" : "browser-entry";
    row.textContent = entry.is_dir ? `${entry.name}/` : entry.name;
    row.addEventListener("click", () => {
      if (entry.is_dir) {
        renderBrowserPanel(container, mount, targetInputId, entry.relative_path, options);
      } else if (!selectDirs) {
        document.getElementById(targetInputId).value = entry.relative_path;
        if (targetInputId === "ctd-path") updateQuickConvertWarning();
        updateSaveStateFromForm();
        closeModal();
      }
    });
    container.appendChild(row);
  }
}

function initBrowser(buttonId, mount, targetInputId, options = {}) {
  document.getElementById(buttonId).addEventListener("click", () => {
    openModal(`Browse ${mount}`, (body) => {
      renderBrowserPanel(body, mount, targetInputId, "", options);
    });
  });
}
```

- [ ] **Step 3: Wire up the new browse buttons and the convert action**

Directly after the existing `initBrowser("browse-quickconvert-xmlcon", "ctd", "quickconvert-xmlcon-path");` line in `app.js`, add:

```javascript
initBrowser("browse-sadcp", "sadcp", "sadcp-path");
initBrowser("browse-codas-contour", "codas", "codas-contour-path", { selectDirs: true });

document.getElementById("run-sadcp-convert").addEventListener("click", async () => {
  const contourDir = document.getElementById("codas-contour-path").value;
  const result = document.getElementById("sadcp-convert-result");
  if (!contourDir) {
    result.textContent = "Pick a CODAS contour directory first.";
    result.className = "error";
    return;
  }
  try {
    const body = await api("/api/sadcp/convert", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ contour_dir: contourDir }),
    });
    document.getElementById("sadcp-path").value = body.sadcp_path;
    updateSaveStateFromForm();
    result.textContent = `Converted. SADCP file set to ${body.sadcp_path}.`;
    result.className = "";
  } catch (e) {
    result.textContent = (e.body && e.body.detail) || "SADCP conversion failed.";
    result.className = "error";
  }
});
```

- [ ] **Step 4: Show the conversion section only when the `codas` mount exists**

Add this function anywhere above its call site in `app.js` (e.g. directly above the final `refreshCastList();` line):

```javascript
async function initSadcpConvertVisibility() {
  const { mounts } = await api("/api/mounts");
  document.getElementById("sadcp-convert-section").hidden = !mounts.includes("codas");
}
```

Change the last line of the file from:

```javascript
refreshCastList();
```

to:

```javascript
refreshCastList();
initSadcpConvertVisibility();
```

- [ ] **Step 5: Run the full Python test suite to check for regressions**

Run: `python -m pytest webapp/tests -v`
Expected: all tests PASS (this task touches no Python files).

- [ ] **Step 6: Manually verify against a real CODAS fixture**

Start the server:

```bash
LDEO_DATA_DIR=/tmp/ldeo_manual_test/data \
LDEO_LADCP_DIR=/tmp/ldeo_manual_test/ladcp \
LDEO_CTD_DIR=/tmp/ldeo_manual_test/ctd \
LDEO_NAV_DIR=/tmp/ldeo_manual_test/nav \
LDEO_SADCP_DIR=/tmp/ldeo_manual_test/sadcp \
LDEO_CODAS_DIR=/home/peter_sha/sourcecode/Nuyina/nuyina_uhdas_codas/output/nuyina_202324050/os150nb \
python -m uvicorn webapp.main:app --reload
```

(create the five `/tmp/ldeo_manual_test/*` directories first with `mkdir -p` — they just need to exist for their mounts to register).

In a browser at `http://127.0.0.1:8000/`:
1. Add a cast, open its editor, confirm the new **SADCP** fieldset appears with a **Browse** button and a **Convert CODAS SADCP data** section (not hidden — the `codas` mount is configured).
2. Click **Convert CODAS SADCP data**, then **Browse** next to "CODAS contour directory". Navigate into `contour/`, click **Use this directory**.
3. Click **Convert CODAS SADCP data**. Confirm the result message shows a `sadcp_convert/os150nb.SADCP.mat` path and the **File** field above is now filled with it.
4. Restart the server without `LDEO_CODAS_DIR` set and confirm the **Convert CODAS SADCP data** section is now hidden, while the plain **File**/**Browse** row for SADCP is still present.

- [ ] **Step 7: Verify the converted file actually loads under Octave**

```bash
docker build -t ldeo-ix-octave:local .
docker run --rm -v /tmp/ldeo_manual_test/data:/data --entrypoint octave-cli ldeo-ix-octave:local --eval "load('/data/sadcp_convert/os150nb.SADCP.mat'); disp(size(u_sadcp)); disp(size(v_sadcp)); disp(size(z_sadcp)); disp(size(tim_sadcp))"
```

Expected: four size vectors print with no error — `u_sadcp`/`v_sadcp` sharing the same `(depth, time)` shape, `z_sadcp` a column vector of that same depth length, `tim_sadcp` a column vector of that same time length. This confirms Octave's `load()` reads the file the same way `loadsadcp.m` will.

- [ ] **Step 8: Commit**

```bash
git add webapp/templates/index.html webapp/static/app.js
git commit -m "$(cat <<'EOF'
feat: add SADCP field and CODAS conversion UI to the cast intake form

The SADCP field itself didn't exist in the form UI before this --
only the backend model/mount did. Also generalizes the file-browser
widget with an optional selectDirs mode, needed to pick a CODAS
contour/ directory rather than a single file.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EsPQKR9bs6vz4Rt8bSMEw
EOF
)"
```

---

### Task 5: Docs — README and user guide

**Files:**
- Modify: `README.md`
- Modify: `webapp/docs/user-guide.md`

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: nothing consumed by other tasks.

- [ ] **Step 1: Update `README.md`'s docker run example**

In the `docker run` example under "Web intake form (default)", add a `codas` mount line after the existing `nav` line:

```bash
docker run --rm -p 8080:8080 \
  -v "$(pwd)/my_cruise:/data" \
  -v "$(pwd)/my_cruise/raw:/ladcp_data" \
  -v "$(pwd)/my_cruise/ctd:/ctd_data" \
  -v "$(pwd)/my_cruise/sadcp:/sadcp_data" \
  -v "$(pwd)/my_cruise/nav:/navigation_data" \
  -v "$(pwd)/my_cruise/codas:/codas_data" \
  ldeo-ix-octave
```

- [ ] **Step 2: Add a README section for the new feature**

Insert a new section after "### Quick-convert (unvalidated)" and before "### Direct Octave CLI":

```markdown
### SADCP conversion from CODAS output

If your voyage ran the University of Hawaii's UHDAS/CODAS shipboard-ADCP
processing (e.g. via the `nuyina_uhdas_codas` sister project), mount that
instrument's CODAS output at `/codas_data` and the SADCP fieldset gets a
**Convert CODAS SADCP data** option. Point it at the instrument's
`contour/` output directory (containing `contour_xy.mat` and
`contour_uv.mat`) and it produces the `.mat` file `loadsadcp.m` expects —
a direct port of `ldeo_ix/mkSADCP.m`, the same conversion LDEO_IX's own
maintainer has always used for this. Unlike Quick-convert above, this
performs no calibration of its own and carries no "unvalidated" caveat —
it only reformats an already-processed CODAS product.

Run it once per voyage (or again after CODAS reprocessing); the same
converted file works for every cast — LDEO_IX picks the relevant time
window out of it at processing time via `p.sadcp_dtok`. Converted files
are written to `data/sadcp_convert/<instrument>.SADCP.mat`.
```

- [ ] **Step 3: Update `webapp/docs/user-guide.md`'s mount table**

Add a row to the table under "## Before you start: mounted directories":

```markdown
| `codas` | CODAS shipboard-ADCP output (optional) — used by SADCP data's **Convert CODAS SADCP data** button. |
```

- [ ] **Step 4: Add a SADCP section to the user guide**

Insert a new section after "## Nav data" and before "## Position / time / bottom-tracking":

```markdown
## SADCP data

Shipboard ADCP (SADCP) data is optional — leave this field blank if your
cruise doesn't have any. If you do have it, **Browse** to an existing
`.mat` file the same way as any other field.

If you instead have CODAS-processed output from the `codas` mount (see
above), the **Convert CODAS SADCP data** section can build that `.mat`
file for you: browse to the instrument's `contour/` directory (containing
`contour_xy.mat` and `contour_uv.mat`) and click **Convert CODAS SADCP
data**. This runs the same conversion LDEO_IX's own `mkSADCP.m` always
has — it covers the whole voyage in one file, not just this cast, so you
only need to do it once and then point every cast's SADCP field at the
same converted file. This section only appears if a `codas` mount was set
up when the container was started.
```

- [ ] **Step 5: Commit**

```bash
git add README.md webapp/docs/user-guide.md
git commit -m "$(cat <<'EOF'
docs: document the CODAS SADCP conversion feature

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014EsPQKR9bs6vz4Rt8bSMEw
EOF
)"
```
