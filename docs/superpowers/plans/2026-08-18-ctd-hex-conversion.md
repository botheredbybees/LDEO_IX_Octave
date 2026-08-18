# CTD Raw-Hex Conversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document pre-converted CTD as the webapp's expected input (unchanged default), and add a clearly-labeled "Quick-convert (unvalidated)" fallback that turns raw Sea-Bird `.hex`+`.XMLCON` into a real `.cnv` file for voyages with no CTD processing at all.

**Architecture:** A new `webapp/quick_convert.py` module wraps `ctdam.conv.decode_hex()` → `CTDData.to_cnv()` (Sea-Bird Scientific's own MIT-licensed `seabirdscientific` toolkit does the actual calibration math under the hood — see the spec). A new `POST /api/quick-convert/ctd` endpoint in `main.py` writes the result under the `data` mount (not `ctd`, which may be read-only) with a fixed `.UNVALIDATED_QUICKCONVERT.cnv` suffix that doubles as the detection signal for a UI warning banner, a preview-mount routing check, and a `validation.py` file-existence fix. New "Quick-convert" button in the CTD fieldset reuses the file-browser widget already built for `ctd`/`nav`/`ladcp`.

**Tech Stack:** FastAPI + Jinja2 + vanilla JS (existing stack, unchanged). New Python dependency: `ctdam==1.13.2` (GPLv3, transitively pulls `seabirdscientific==2.7.8`, MIT). No Dockerfile/Python-version changes needed — the base image (`gnuoctave/octave:9.2.0`, Ubuntu 24.04) already ships Python 3.12.3, which satisfies `ctdam`'s `>=3.12` requirement.

**Spec:** `docs/superpowers/specs/2026-08-18-ctd-hex-conversion-design.md` (also published to Confluence: https://ausantarctic.atlassian.net/wiki/spaces/LS/pages/2515173377)

## Global Constraints

- The intake form's documented default expectation stays pre-converted CTD input — this plan does not change that, it adds a fallback alongside it.
- Every quick-converted output file gets the fixed suffix `.UNVALIDATED_QUICKCONVERT.cnv` — this exact string is load-bearing (drives UI warning detection, preview-mount routing, and the validation fix), not just a label. Do not change it without updating all four call sites (worker output naming, frontend suffix check in the Preview handler, frontend warning-banner check, `validation.py`'s mount check).
- Quick-convert output is written under `config.MOUNTS["data"] / "quick_convert"`, never under the `ctd` mount (which may be a read-only bind mount of raw ship data in practice).
- `ctdam` requires Python ≥3.12. The Docker image already provides this (verified: Ubuntu 24.04, stock `python3` is 3.12.3) — no Dockerfile changes needed. This dev machine's default Python is 3.10, so any test that actually imports `ctdam` must run inside a container, not bare on the host — see Task 2's testing note.
- No accuracy/validation test suite for `ctdam`'s conversion output — asserting it matches Sea-Bird's official output would imply a scientific-correctness claim this feature explicitly disclaims (see spec, "Explicitly out of scope").
- Every button/label/filename touching this feature must say "unvalidated"/"emergency use only" — this is a non-negotiable requirement from the spec, not a nice-to-have to trim under time pressure.

---

### Task 1: Document pre-converted CTD as the expected default input

**Files:**
- Modify: `README.md` (Usage → Web intake form section, after the existing `docker run` example block, before the "No authentication" paragraph — currently ends around line 62)

**Interfaces:**
- Produces: nothing consumed by later tasks — this is documentation only, no code, no new symbols. Included as its own task because it's independently reviewable/mergeable and doesn't need anything from Tasks 2+.

This task implements decision "B" from the spec: making an already-true-but-implicit expectation explicit. No behavior changes.

- [ ] **Step 1: Add the prerequisite paragraph**

In `README.md`, immediately after the closing ` ``` ` of the `docker run` example block in the "Web intake form (default)" section, add:

```markdown
**CTD input must already be converted.** The form's CTD field expects an
already-converted, decimated ASCII/`.cnv` time series (the standard
output of Sea-Bird's own SBE Data Processing software) — not a raw
`.hex` file. If your voyage's CTD data was never run through that
conversion step, see "Quick-convert" below for a fallback; for anyone
who does have Sea-Bird's software, that's still the right way to get a
science-grade converted file.
```

- [ ] **Step 2: Verify the file renders correctly**

Run: `grep -A6 "CTD input must already" README.md`
Expected: the paragraph you just added, unchanged.

- [ ] **Step 3: Commit**

```bash
cd /home/peter_sha/sourcecode/Nuyina/LDEO_IX_Octave
git add README.md
git commit -m "docs: document pre-converted CTD as the intake form's expected input"
```

---

### Task 2: `webapp/quick_convert.py` — hex+XMLCON to `.cnv` conversion

**Files:**
- Create: `webapp/quick_convert.py`
- Modify: `webapp/requirements.txt` (add `ctdam==1.13.2`)
- Modify: `NOTICE.md` (new section documenting `ctdam`/`seabirdscientific`)
- Test: `webapp/tests/test_quick_convert.py`

**Interfaces:**
- Produces: `webapp.quick_convert.QUICKCONVERT_SUFFIX` (str constant, `".UNVALIDATED_QUICKCONVERT.cnv"`); `webapp.quick_convert.convert(hex_path: Path, xmlcon_path: Path, data_mount_root: Path) -> str` — performs the conversion, writes the output under `data_mount_root / "quick_convert"`, returns the `data`-mount-relative path as a string (e.g. `"quick_convert/202324050_002.UNVALIDATED_QUICKCONVERT.cnv"`). Raises `QuickConvertError(str)` (new exception class, also defined in this module) on any failure — Task 3's endpoint catches this specifically to return a clean 400 rather than a 500.

**Testing note (read before starting):** `ctdam` requires Python ≥3.12; this dev machine's default `python3` is 3.10. Build the image once, then iterate by bind-mounting the live `webapp/` directory over the copied one and running pytest inside the container — much faster than a full rebuild per edit:

```bash
cd /home/peter_sha/sourcecode/Nuyina/LDEO_IX_Octave
docker build -t ldeo-ix-octave:local .        # once, after Step 1 below
docker run --rm --entrypoint bash \
  -v "$(pwd):/workspace" -w /workspace \
  -e PYTHONPATH=/workspace \
  ldeo-ix-octave:local \
  -c "python3 -m pytest webapp/tests/test_quick_convert.py -v"
```

- [ ] **Step 1: Add the dependency**

In `webapp/requirements.txt`, add a new line:

```
ctdam==1.13.2
```

- [ ] **Step 2: Document the new dependencies in NOTICE.md**

Append to `NOTICE.md`:

```markdown

## Quick-convert dependencies

The webapp's "Quick-convert (unvalidated)" CTD fallback (see
`webapp/quick_convert.py`) uses two third-party Python packages, both
with clear, permissive-enough licenses (unlike `ldeo_ix/` above, neither
is a redistribution-status question):

- [`ctdam`](https://github.com/DAM-CTD-Software/ctdam) — GPLv3. Used as
  a normal Python dependency (installed via pip, not modified or
  vendored), not redistributed as part of this project's own source.
- [`seabirdscientific`](https://github.com/Sea-BirdScientific/seabirdscientific) —
  MIT. Sea-Bird Scientific's own official community toolkit; `ctdam`
  depends on it for the actual hex-decoding/calibration math. Pulled in
  transitively via `ctdam`, not a direct dependency of this repo.
```

- [ ] **Step 3: Write the failing test**

Create `webapp/tests/test_quick_convert.py`:

```python
from pathlib import Path

import pytest

from webapp import quick_convert

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "test_data" / "202324050_nuyina" / "ctd" / "seasave_raw"
FIXTURE_HEX = FIXTURE_DIR / "202324050_002.hex"
FIXTURE_XMLCON = FIXTURE_DIR / "202324050_002.XMLCON"


def test_convert_writes_cnv_under_quick_convert_dir(tmp_path):
    if not FIXTURE_HEX.is_file():
        pytest.skip("test_data/ fixture not present in this checkout")

    result = quick_convert.convert(FIXTURE_HEX, FIXTURE_XMLCON, tmp_path)

    assert result == "quick_convert/202324050_002.UNVALIDATED_QUICKCONVERT.cnv"
    written = tmp_path / "quick_convert" / "202324050_002.UNVALIDATED_QUICKCONVERT.cnv"
    assert written.is_file()
    assert written.stat().st_size > 0


def test_convert_output_is_previewable(tmp_path):
    if not FIXTURE_HEX.is_file():
        pytest.skip("test_data/ fixture not present in this checkout")

    from webapp import delimited_parser

    result = quick_convert.convert(FIXTURE_HEX, FIXTURE_XMLCON, tmp_path)
    written = tmp_path / result

    preview = delimited_parser.sniff_and_preview(written)

    assert preview.fields_per_line > 0
    assert len(preview.preview_rows) > 0


def test_convert_raises_quick_convert_error_for_missing_hex(tmp_path):
    with pytest.raises(quick_convert.QuickConvertError):
        quick_convert.convert(tmp_path / "does_not_exist.hex", tmp_path / "does_not_exist.XMLCON", tmp_path)
```

- [ ] **Step 4: Run the tests to verify they fail**

Run (inside the container, per the testing note above):
```bash
python3 -m pytest webapp/tests/test_quick_convert.py -v
```
Expected: `ModuleNotFoundError: No module named 'webapp.quick_convert'` (or import error) — the module doesn't exist yet.

- [ ] **Step 5: Write the implementation**

Create `webapp/quick_convert.py`:

```python
from pathlib import Path

from ctdam.conv import decode_hex

QUICKCONVERT_SUFFIX = ".UNVALIDATED_QUICKCONVERT.cnv"


class QuickConvertError(Exception):
    pass


def convert(hex_path: Path, xmlcon_path: Path, data_mount_root: Path) -> str:
    if not hex_path.is_file():
        raise QuickConvertError(f"{hex_path} not found")
    if not xmlcon_path.is_file():
        raise QuickConvertError(f"{xmlcon_path} not found")

    output_dir = data_mount_root / "quick_convert"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_name = f"{hex_path.stem}{QUICKCONVERT_SUFFIX}"
    output_path = output_dir / output_name

    try:
        ctd_data = decode_hex(hex_path, xmlcon_path)
        ctd_data.to_cnv(str(output_path))
    except Exception as exc:
        raise QuickConvertError(f"could not convert {hex_path.name}: {exc}") from exc

    return f"quick_convert/{output_name}"
```

- [ ] **Step 6: Run the tests to verify they pass**

Run (inside the container):
```bash
python3 -m pytest webapp/tests/test_quick_convert.py -v
```
Expected: all 3 tests PASS. If `test_convert_output_is_previewable` fails because `sniff_and_preview` finds 0 data rows, inspect the generated `.cnv` file's actual header/data layout by hand (`docker run ... cat /workspace/<tmp output path>` won't work since `tmp_path` is ephemeral — instead write the output to a fixed path temporarily while debugging, e.g. call `quick_convert.convert(FIXTURE_HEX, FIXTURE_XMLCON, Path("/workspace/debug_out"))` from a throwaway script) and adjust `to_cnv`'s call if `ctdam` needs an explicit option to write plain space-delimited data rows rather than something `sniff_and_preview` can't parse — check `ctdam`'s `CTDData.to_cnv` signature (`webapp/../` isn't available at runtime for browsing `ctdam`'s source; use `python3 -c "import ctdam.parser.ctddata as m; help(m.CTDData.to_cnv)"` inside the container if this happens).

- [ ] **Step 7: Commit**

```bash
git add webapp/quick_convert.py webapp/tests/test_quick_convert.py webapp/requirements.txt NOTICE.md
git commit -m "feat: add webapp/quick_convert.py (hex+XMLCON -> .cnv via ctdam)"
```

---

### Task 3: `POST /api/quick-convert/ctd` endpoint

**Files:**
- Modify: `webapp/main.py`
- Test: `webapp/tests/test_api_quick_convert.py`

**Interfaces:**
- Consumes: `webapp.quick_convert.convert(hex_path, xmlcon_path, data_mount_root) -> str` and `webapp.quick_convert.QuickConvertError` (Task 2).
- Produces: `POST /api/quick-convert/ctd` — JSON body `{"hex_path": "<ctd-mount-relative>", "xmlcon_path": "<ctd-mount-relative>"}`, returns `{"ctd_path": "<data-mount-relative, e.g. quick_convert/foo.UNVALIDATED_QUICKCONVERT.cnv>"}` on success (200), or `{"detail": "<message>"}` (400) on failure. Later tasks (Task 5, frontend) call this endpoint and use the exact `ctd_path` key.

This task's tests don't need `ctdam`/Python 3.12 at all — they exercise the endpoint's path-resolution and error-handling logic against a fake `quick_convert.convert`, matching how `test_api_generate.py` tests `/api/generate` without needing real LDEO_IX. Run these on the host normally:
```bash
cd /home/peter_sha/sourcecode/Nuyina/LDEO_IX_Octave
python3 -m pip install -r webapp/requirements-dev.txt   # if not already done this session
python3 -m pytest webapp/tests/test_api_quick_convert.py -v
```
(Skip `ctdam` here — since this test file monkeypatches `quick_convert.convert` directly, it never imports the real `ctdam` package, so Python 3.10 is fine for this one file even though `webapp/requirements.txt` as a whole now lists a 3.12-only package. If `pip install -r webapp/requirements-dev.txt` fails trying to resolve `ctdam` under 3.10, run `pip install -r webapp/requirements-dev.txt --no-deps` for `fastapi`/`httpx`/`pytest` individually instead, or just confirm the existing venv from prior sessions already has them and skip reinstalling.)

- [ ] **Step 1: Write the failing tests**

Create `webapp/tests/test_api_quick_convert.py`:

```python
from fastapi.testclient import TestClient

from webapp import config, main, quick_convert


def test_quick_convert_ctd_success(tmp_path, monkeypatch):
    ctd_mount = tmp_path / "ctd"
    data_mount = tmp_path / "data"
    ctd_mount.mkdir()
    data_mount.mkdir()
    (ctd_mount / "cast.hex").write_text("fake hex")
    (ctd_mount / "cast.XMLCON").write_text("fake xmlcon")
    monkeypatch.setitem(config.MOUNTS, "ctd", ctd_mount)
    monkeypatch.setitem(config.MOUNTS, "data", data_mount)

    def _fake_convert(hex_path, xmlcon_path, data_mount_root):
        assert hex_path == ctd_mount / "cast.hex"
        assert xmlcon_path == ctd_mount / "cast.XMLCON"
        assert data_mount_root == data_mount
        return "quick_convert/cast.UNVALIDATED_QUICKCONVERT.cnv"

    monkeypatch.setattr(quick_convert, "convert", _fake_convert)

    client = TestClient(main.app)
    response = client.post(
        "/api/quick-convert/ctd",
        json={"hex_path": "cast.hex", "xmlcon_path": "cast.XMLCON"},
    )

    assert response.status_code == 200
    assert response.json() == {"ctd_path": "quick_convert/cast.UNVALIDATED_QUICKCONVERT.cnv"}


def test_quick_convert_ctd_rejects_path_traversal(tmp_path, monkeypatch):
    ctd_mount = tmp_path / "ctd"
    ctd_mount.mkdir()
    monkeypatch.setitem(config.MOUNTS, "ctd", ctd_mount)
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path / "data")

    client = TestClient(main.app)
    response = client.post(
        "/api/quick-convert/ctd",
        json={"hex_path": "../../etc/passwd", "xmlcon_path": "cast.XMLCON"},
    )

    assert response.status_code == 400


def test_quick_convert_ctd_surfaces_conversion_error(tmp_path, monkeypatch):
    ctd_mount = tmp_path / "ctd"
    data_mount = tmp_path / "data"
    ctd_mount.mkdir()
    data_mount.mkdir()
    (ctd_mount / "cast.hex").write_text("fake hex")
    (ctd_mount / "cast.XMLCON").write_text("fake xmlcon")
    monkeypatch.setitem(config.MOUNTS, "ctd", ctd_mount)
    monkeypatch.setitem(config.MOUNTS, "data", data_mount)

    def _fake_convert(hex_path, xmlcon_path, data_mount_root):
        raise quick_convert.QuickConvertError("could not convert cast.hex: bad checksum")

    monkeypatch.setattr(quick_convert, "convert", _fake_convert)

    client = TestClient(main.app)
    response = client.post(
        "/api/quick-convert/ctd",
        json={"hex_path": "cast.hex", "xmlcon_path": "cast.XMLCON"},
    )

    assert response.status_code == 400
    assert "bad checksum" in response.json()["detail"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest webapp/tests/test_api_quick_convert.py -v`
Expected: `404 Not Found` (route doesn't exist yet) on all three, or a collection error if `quick_convert` isn't importable — if the latter, confirm Task 2 is committed first.

- [ ] **Step 3: Add the endpoint**

In `webapp/main.py`, add near the other `/api/*` route functions (after `preview_file`, before `scan_ladcp`):

```python
from pydantic import BaseModel

from webapp import quick_convert


class QuickConvertCtdRequest(BaseModel):
    hex_path: str
    xmlcon_path: str


@app.post("/api/quick-convert/ctd")
def quick_convert_ctd(body: QuickConvertCtdRequest):
    ctd_mount = config.MOUNTS.get("ctd")
    data_mount = config.MOUNTS.get("data")
    if ctd_mount is None or not ctd_mount.is_dir():
        raise HTTPException(status_code=404, detail="ctd mount not available")
    if data_mount is None or not data_mount.is_dir():
        raise HTTPException(status_code=404, detail="data mount not available")

    try:
        resolved_hex = paths.resolve_within(ctd_mount, body.hex_path)
        resolved_xmlcon = paths.resolve_within(ctd_mount, body.xmlcon_path)
    except paths.PathOutsideMountError:
        raise HTTPException(status_code=400, detail="path is outside the allowed directory")

    try:
        ctd_path = quick_convert.convert(resolved_hex, resolved_xmlcon, data_mount)
    except quick_convert.QuickConvertError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"ctd_path": ctd_path}
```

(`BaseModel`, `paths`, `HTTPException`, `config` are already imported at the top of `main.py` except `BaseModel` and `quick_convert` — add those two imports; check the existing import block first so you don't duplicate `from pydantic import BaseModel` if it's somehow already there.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest webapp/tests/test_api_quick_convert.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Run the full existing test suite to check for regressions**

Run: `python3 -m pytest webapp/tests -v`
Expected: all tests pass (53 pre-existing + 3 new from Task 2, assuming Task 2's tests were run in the container and are being skipped here via the `pytest.skip` guard if `ctdam` isn't importable on the host — that's fine, they're not regressions).

- [ ] **Step 6: Commit**

```bash
git add webapp/main.py webapp/tests/test_api_quick_convert.py
git commit -m "feat: add POST /api/quick-convert/ctd endpoint"
```

---

### Task 4: Fix `validation.py`'s CTD mount check for quick-converted files

**Files:**
- Modify: `webapp/validation.py`
- Test: `webapp/tests/test_validation.py`

**Interfaces:**
- Consumes: `webapp.quick_convert.QUICKCONVERT_SUFFIX` (Task 2).
- Produces: nothing new consumed elsewhere — this is a correctness fix to existing behavior.

Without this fix, a cast whose `ctd` field holds a quick-converted `data`-mount-relative path (e.g. `quick_convert/foo.UNVALIDATED_QUICKCONVERT.cnv`) gets a spurious "not found under ctd mount" warning from `/api/generate`'s validation pass, because `validate_session`'s `_FILE_FIELDS` list always checks the `ctd` field against the `ctd` mount specifically. The file genuinely exists — it's just under `data`, not `ctd`.

- [ ] **Step 1: Write the failing test**

Add to `webapp/tests/test_validation.py` (check the existing file first for its exact import/fixture style and match it — likely `from webapp import config, validation` and `from webapp.models import CastEntry, CruiseSession`):

```python
def test_quick_converted_ctd_checked_against_data_mount_not_ctd_mount(tmp_path, monkeypatch):
    data_mount = tmp_path / "data"
    ctd_mount = tmp_path / "ctd"
    data_mount.mkdir()
    ctd_mount.mkdir()
    quick_convert_dir = data_mount / "quick_convert"
    quick_convert_dir.mkdir()
    (quick_convert_dir / "cast.UNVALIDATED_QUICKCONVERT.cnv").write_text("fake cnv")
    monkeypatch.setitem(config.MOUNTS, "data", data_mount)
    monkeypatch.setitem(config.MOUNTS, "ctd", ctd_mount)

    session = CruiseSession(casts=[CastEntry(
        ladcpdo="003DL000.000", ladcpup="003UL000.000",
        ladcp_station=3, ladcp_cast=1, lat=-15.5, lon=-150.2,
        time_start=[2015, 4, 11, 17, 36, 23.0], time_end=[2015, 4, 11, 21, 9, 42.0],
        ctd="quick_convert/cast.UNVALIDATED_QUICKCONVERT.cnv",
    )])

    result = validation.validate_session(session)

    assert result.warnings == {}
```

(Check `webapp/tests/test_validation.py`'s top for the exact existing import lines and any shared fixture/helper for building a minimal valid `CastEntry` — e.g. `test_api_generate.py`'s `_valid_cast_payload()` pattern might already have an equivalent in this file; reuse it rather than duplicating the required-fields list if one exists.)

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest webapp/tests/test_validation.py -v -k quick_converted`
Expected: FAIL — `result.warnings` contains a `{cast.id: ["quick_convert/cast.UNVALIDATED_QUICKCONVERT.cnv not found under ctd mount"]}` entry, since the current code checks the wrong mount.

- [ ] **Step 3: Fix `validate_session`**

In `webapp/validation.py`, the current loop reads:

```python
        cast_warnings = []
        for mount_name, field_name in _FILE_FIELDS:
            relative = getattr(cast, field_name)
            if not relative:
                continue
            mount_root = config.MOUNTS.get(mount_name)
```

Change the `mount_root` lookup to account for the quick-convert suffix on the `ctd` field specifically:

```python
        cast_warnings = []
        for mount_name, field_name in _FILE_FIELDS:
            relative = getattr(cast, field_name)
            if not relative:
                continue
            if field_name == "ctd" and relative.endswith(quick_convert.QUICKCONVERT_SUFFIX):
                mount_root = config.MOUNTS.get("data")
            else:
                mount_root = config.MOUNTS.get(mount_name)
```

Add the import at the top of the file: `from webapp import quick_convert` (alongside the existing `from webapp import config, paths`).

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest webapp/tests/test_validation.py -v -k quick_converted`
Expected: PASS.

- [ ] **Step 5: Run the full validation test file to check for regressions**

Run: `python3 -m pytest webapp/tests/test_validation.py -v`
Expected: all tests pass, including the pre-existing ones (unaffected — the new branch only triggers for `ctd` fields ending in the quick-convert suffix).

- [ ] **Step 6: Commit**

```bash
git add webapp/validation.py webapp/tests/test_validation.py
git commit -m "fix: check quick-converted CTD files against the data mount, not ctd"
```

---

### Task 5: Frontend — Quick-convert button, warning banner, preview routing

**Files:**
- Modify: `webapp/templates/index.html`
- Modify: `webapp/static/app.js`
- Modify: `webapp/static/style.css`

**Interfaces:**
- Consumes: `POST /api/quick-convert/ctd` (Task 3, returns `{"ctd_path": "..."}`); the existing `initBrowser`/`renderBrowserPanel` file-browser widget and `renderPreview` function (already in `app.js` from the prior file-browser work); `QUICKCONVERT_SUFFIX` value `.UNVALIDATED_QUICKCONVERT.cnv` (Task 2 — hardcode this exact string in JS; there's no API endpoint exposing it as a constant, and adding one just for this would be overkill for a single fixed string used in 2-3 places).
- Produces: nothing consumed by later tasks — this is the last functional task; Task 6 is verification only.

- [ ] **Step 1: Add the Quick-convert button and its file-pickers to the CTD fieldset**

In `webapp/templates/index.html`, inside the `<fieldset><legend>CTD</legend>...` block, immediately after the existing `<div class="file-browser" id="ctd-browser" hidden></div>` line, add:

```html
      <div id="ctd-quickconvert-warning" class="warning" hidden>
        ⚠ This CTD file was generated by Quick-convert — unvalidated,
        not Sea-Bird-equivalent, not for publication-grade science. See
        the README for details.
      </div>

      <details>
        <summary>Quick-convert raw hex (unvalidated, emergency use only)</summary>
        <label>Raw .hex file <input name="quickconvert_hex" id="quickconvert-hex-path"></label>
        <button type="button" id="browse-quickconvert-hex">Browse</button>
        <div class="file-browser" id="quickconvert-hex-browser" hidden></div>
        <label>.XMLCON file <input name="quickconvert_xmlcon" id="quickconvert-xmlcon-path"></label>
        <button type="button" id="browse-quickconvert-xmlcon">Browse</button>
        <div class="file-browser" id="quickconvert-xmlcon-browser" hidden></div>
        <button type="button" id="run-quickconvert">Quick-convert (unvalidated, emergency use only)</button>
        <div id="quickconvert-result"></div>
      </details>
```

(No visual mockup companion needed here — this is a small, self-contained addition following the existing fieldset/label/button pattern already used throughout this file; describing it in text is clear enough.)

- [ ] **Step 2: Wire the two new file-browsers and the warning-banner check into `app.js`**

In `webapp/static/app.js`, immediately after the existing four `initBrowser(...)` calls (`browse-ctd`, `browse-nav`, `browse-ladcpdo`, `browse-ladcpup`), add:

```js
initBrowser("browse-quickconvert-hex", "ctd", "quickconvert-hex-path", "quickconvert-hex-browser");
initBrowser("browse-quickconvert-xmlcon", "ctd", "quickconvert-xmlcon-path", "quickconvert-xmlcon-browser");

const QUICKCONVERT_SUFFIX = ".UNVALIDATED_QUICKCONVERT.cnv";

function updateQuickConvertWarning() {
  const value = document.getElementById("ctd-path").value;
  document.getElementById("ctd-quickconvert-warning").hidden = !value.endsWith(QUICKCONVERT_SUFFIX);
}

document.getElementById("ctd-path").addEventListener("input", updateQuickConvertWarning);

document.getElementById("run-quickconvert").addEventListener("click", async () => {
  const hexPath = document.getElementById("quickconvert-hex-path").value;
  const xmlconPath = document.getElementById("quickconvert-xmlcon-path").value;
  const result = document.getElementById("quickconvert-result");
  if (!hexPath || !xmlconPath) {
    result.textContent = "Pick both a .hex file and its .XMLCON file first.";
    result.className = "error";
    return;
  }
  try {
    const body = await api("/api/quick-convert/ctd", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hex_path: hexPath, xmlcon_path: xmlconPath }),
    });
    document.getElementById("ctd-path").value = body.ctd_path;
    updateQuickConvertWarning();
    result.textContent = `Converted. CTD file set to ${body.ctd_path} — remember, this is unvalidated.`;
    result.className = "warning";
  } catch (e) {
    result.textContent = (e.body && e.body.detail) || "Quick-convert failed.";
    result.className = "error";
  }
});
```

- [ ] **Step 3: Route the Preview button to the right mount for quick-converted files**

In `webapp/static/app.js`, find the existing line:

```js
document.getElementById("preview-ctd").addEventListener("click", () => {
  renderPreview("ctd", "ctd-path", "ctd-preview", ["time", "pressure", "temperature", "salinity"]);
});
```

Replace it with:

```js
document.getElementById("preview-ctd").addEventListener("click", () => {
  const ctdPath = document.getElementById("ctd-path").value;
  const mount = ctdPath.endsWith(QUICKCONVERT_SUFFIX) ? "data" : "ctd";
  renderPreview(mount, "ctd-path", "ctd-preview", ["time", "pressure", "temperature", "salinity"]);
});
```

(Leave the `preview-nav` handler untouched — nav files are never quick-converted.)

- [ ] **Step 4: Also call the warning check when a normal Browse selects a CTD file**

The existing `renderBrowserPanel` function (from the file-browser work) sets `document.getElementById(targetInputId).value = entry.relative_path;` when a file is clicked. Find that line and change it to also refresh the warning banner when the target is the CTD input specifically:

```js
      } else {
        document.getElementById(targetInputId).value = entry.relative_path;
        if (targetInputId === "ctd-path") updateQuickConvertWarning();
        panel.hidden = true;
      }
```

(This covers the case where a user manually Browses to a `.UNVALIDATED_QUICKCONVERT.cnv` file left over from an earlier session, or clears it by picking a normal file — the banner should reflect whatever's actually in the box, not just what Quick-convert itself just set.)

- [ ] **Step 5: Verify no JS syntax errors**

Run: `node --check webapp/static/app.js` (Node's syntax checker; doesn't need any of the project's own dependencies, just confirms the file parses — if `node` isn't available, skip this step and rely on Task 6's live browser check instead, which will surface any syntax error immediately as a console error on page load).

- [ ] **Step 6: Commit**

```bash
git add webapp/templates/index.html webapp/static/app.js
git commit -m "feat: wire up Quick-convert UI (button, warning banner, preview routing)"
```

---

### Task 6: Docker build/run verification + Playwright UI check + labeling doc

**Files:**
- No new files — this task verifies Tasks 1-5 end-to-end and adds the one remaining labeling requirement from the spec (a webapp-facing docs note, distinct from Task 1's README prerequisite paragraph).
- Modify: `README.md` (new short subsection, "Quick-convert (unvalidated)")

**Interfaces:**
- Consumes: everything from Tasks 1-5.
- Produces: nothing — terminal verification task.

- [ ] **Step 1: Build the image with the new dependency**

```bash
cd /home/peter_sha/sourcecode/Nuyina/LDEO_IX_Octave
docker build -t ldeo-ix-octave:local .
```
Expected: build succeeds (this also re-confirms `pip install -r webapp/requirements.txt` resolves `ctdam` cleanly under the image's real Python 3.12.3 — the first real end-to-end proof, since Task 2's container-based test run already exercised this, but a full rebuild from a clean `requirements.txt` state is worth doing once more here in case Task 2-5's commits were made against a stale image).

- [ ] **Step 2: Run the full test suite inside the container**

```bash
docker run --rm --entrypoint bash \
  -v "$(pwd):/workspace" -w /workspace \
  -e PYTHONPATH=/workspace \
  ldeo-ix-octave:local \
  -c "python3 -m pytest webapp/tests -v"
```
Expected: all tests pass (pre-existing 53+ plus every test added in Tasks 2-4), now including the ones Task 2's testing note had you run standalone earlier.

- [ ] **Step 3: Start the real server against real test data**

```bash
docker run --rm -p 8080:8080 \
  -v "$(pwd)/test_data/202324050_nuyina/ctd/seasave_raw:/ctd_data" \
  -v "$(pwd)/test_data/202324050_nuyina:/data" \
  ldeo-ix-octave:local
```

- [ ] **Step 4: Exercise the feature via Playwright**

Navigate to `http://localhost:8080/`, click "Add cast", expand the "Quick-convert raw hex" details section, Browse to pick `202324050_002.hex` for the raw-hex field and `202324050_002.XMLCON` for the XMLCON field, click "Quick-convert (unvalidated, emergency use only)". Confirm:
- The `ctd-path` input's value becomes `quick_convert/202324050_002.UNVALIDATED_QUICKCONVERT.cnv`.
- The warning banner (`#ctd-quickconvert-warning`) becomes visible.
- Clicking "Preview / map columns" shows real column data (not an error) — this confirms the mount-routing fix from Task 5 Step 3 actually works against a live server, not just the unit-level assumption that `/api/preview/{mount}` is generic.
- Clicking "Save cast" then "Generate set_cast_params.m" succeeds with **no warning** about the CTD file (confirms Task 4's validation fix).

- [ ] **Step 5: Stop the container**

```bash
docker stop $(docker ps -q --filter ancestor=ldeo-ix-octave:local)
```

- [ ] **Step 6: Add the webapp-facing labeling doc (spec's 4th labeling requirement)**

In `README.md`, immediately after the "CTD input must already be converted" paragraph added in Task 1, add:

```markdown

### Quick-convert (unvalidated)

For voyages with no CTD processing at all, the CTD fieldset has a
"Quick-convert raw hex" option that turns a raw `.hex`+`.XMLCON` pair
into a usable `.cnv` file automatically, using the open-source `ctdam`
library. **This is not Sea-Bird-equivalent and its output should never
be treated as publication-grade without independent verification** —
it exists purely so a cast with no other CTD conversion available isn't
a hard blocker. Quick-converted files are always named
`<original>.UNVALIDATED_QUICKCONVERT.cnv` so the provenance travels with
the file even outside this tool.
```

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs: document the Quick-convert fallback feature"
```

- [ ] **Step 8: Push**

```bash
git push origin master
```
