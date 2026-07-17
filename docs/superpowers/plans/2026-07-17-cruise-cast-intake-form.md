# Cruise/Cast Intake Form Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python/FastAPI web app, bundled into the `ldeo-ix-octave` Docker image, that generates `set_cast_params.m` for a whole cruise (multiple casts) by inferring fields from CTD/raw/nav/prior-output files wherever possible.

**Architecture:** A new `webapp/` package (FastAPI + Jinja2 + vanilla JS, no build step) with pure-logic modules (path safety, file parsing/sniffing, filename inference, netCDF reading, M-code generation, validation) each independently unit-tested, wired together by a thin API layer and server-rendered pages. The Docker image gains Python and switches its default entrypoint from `octave-cli` to the web server.

**Tech Stack:** Python 3, FastAPI, uvicorn, Jinja2, pydantic, scipy (netCDF3 reading), pytest + httpx (testing).

## Global Constraints

- No Node/build toolchain — server-rendered Jinja2 templates + vanilla JS only.
- `docker run ldeo-ix-octave` starts the web server by default; `octave-cli` remains reachable via `docker run ldeo-ix-octave octave-cli` or `docker exec`.
- Mounts: `/data` (required — working dir, session sidecar, output), `/ladcp_data`, `/ctd_data`, `/sadcp_data`, `/navigation_data` (all optional; backend only offers browsing for mounts actually present).
- Every file-browse/read operation MUST resolve the requested path and assert it stays under its declared mount root before touching disk — this is a hard requirement (path-traversal defense), not optional polish.
- The tool is write-only: it never parses an existing hand-written `set_cast_params.m` back into the form.
- Generation backs up any existing `/data/set_cast_params.m` (timestamped) before overwriting.
- The session sidecar (`/data/.cruise_intake_session.json`) is intake-tool state only — never read by LDEO_IX/`process_cast.m`.
- No changes to `ldeo_ix/` in this slice — no `CHANGES.md` entry needed.
- NetCDF reading assumes classic NetCDF3 format via `scipy.io.netcdf_file` — confirmed against a real output file in Task 6; if wrong, swap the library there without touching other modules.

---

## Task 1: Web server skeleton + Docker wiring

**Files:**
- Create: `webapp/__init__.py`
- Create: `webapp/main.py`
- Create: `webapp/requirements.txt`
- Create: `webapp/requirements-dev.txt`
- Modify: `Dockerfile`
- Test: manual (Docker build + curl), no unit test (nothing to unit-test yet — pure wiring)

**Interfaces:**
- Produces: `webapp.main.app` (a `FastAPI` instance) — later tasks call `app.include_router(...)` and add routes to it.

- [ ] **Step 1: Create the `webapp` package and minimal app**

`webapp/__init__.py`:
```python
```

`webapp/main.py`:
```python
from fastapi import FastAPI

app = FastAPI(title="LDEO_IX Cruise/Cast Intake")


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 2: Add dependency files**

`webapp/requirements.txt`:
```
fastapi==0.115.*
uvicorn[standard]==0.32.*
jinja2==3.1.*
scipy==1.14.*
python-multipart==0.0.*
```

`webapp/requirements-dev.txt`:
```
-r requirements.txt
pytest==8.3.*
httpx==0.27.*
```

- [ ] **Step 3: Install dev dependencies locally and verify the app imports**

Run: `python -m pip install -r webapp/requirements-dev.txt`
Then: `python -c "from webapp.main import app; print(app.title)"`
Expected output: `LDEO_IX Cruise/Cast Intake`

- [ ] **Step 4: Wire Python and the web app into the Dockerfile**

Modify `Dockerfile` — replace the whole file with:

```dockerfile
FROM docker.io/gnuoctave/octave:9.2.0

LABEL org.opencontainers.image.title="ldeo-ix-octave" \
      org.opencontainers.image.description="LDEO_IX LADCP processing (Visbeck/Krahmann/Marin/Grelet), patched to run under GNU Octave" \
      org.opencontainers.image.licenses="MIT"

# Third-party LADCP processing code (see NOTICE.md) plus headless plotting
# stubs (real MATLAB/Octave has a display; this image doesn't).
COPY ldeo_ix/ /opt/ldeo_ix/
COPY stubs/   /opt/stubs/

# Function-name resolution prefers the path over builtins, so the stubs
# shadow Octave's real plotting functions without touching ldeo_ix/ itself.
ENV OCTAVE_PATH=/opt/stubs:/opt/ldeo_ix

# Web intake app (forms that generate set_cast_params.m) -- see webapp/.
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*
COPY webapp/requirements.txt /opt/webapp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /opt/webapp/requirements.txt
COPY webapp/ /opt/webapp/
ENV PYTHONPATH=/opt

EXPOSE 8080

# Mount your cruise/cast directory (containing set_cast_params.m and the
# raw data -- see examples/ and README.md) here. Optional source-data
# mounts: /ladcp_data, /ctd_data, /sadcp_data, /navigation_data.
WORKDIR /data

ENTRYPOINT ["/opt/webapp/entrypoint.sh"]
CMD ["serve"]
```

- [ ] **Step 5: Add the entrypoint script that switches between the web server and the original CLI**

Create `webapp/entrypoint.sh`:
```bash
#!/bin/sh
set -e

if [ "$1" = "serve" ]; then
  exec uvicorn webapp.main:app --host 0.0.0.0 --port 8080
elif [ "$1" = "octave-cli" ]; then
  shift
  exec octave-cli --no-gui "$@"
else
  exec "$@"
fi
```

Run: `chmod +x webapp/entrypoint.sh`

- [ ] **Step 6: Build the image and verify both entry paths work**

Run: `docker build -t ldeo-ix-octave:local .`

Run: `docker run --rm -d -p 8080:8080 --name ldeo-web -v "$(pwd)/examples:/data" ldeo-ix-octave:local`
Run: `curl -s http://localhost:8080/health`
Expected output: `{"status":"ok"}`
Run: `docker stop ldeo-web`

Run: `docker run --rm ldeo-ix-octave:local octave-cli --eval "disp('cli still works')"`
Expected output: `cli still works`

- [ ] **Step 7: Commit**

```bash
git add webapp/__init__.py webapp/main.py webapp/requirements.txt webapp/requirements-dev.txt webapp/entrypoint.sh Dockerfile
git commit -m "feat: add web app skeleton, switch default entrypoint to web server"
```

---

## Task 2: Mount configuration and safe path resolution

**Files:**
- Create: `webapp/config.py`
- Create: `webapp/paths.py`
- Test: `webapp/tests/test_paths.py`

**Interfaces:**
- Consumes: nothing (foundational module)
- Produces: `config.MOUNTS: dict[str, Path]` (keys: `"data"`, `"ladcp"`, `"ctd"`, `"sadcp"`, `"nav"`), `config.available_mounts() -> dict[str, Path]`, `config.SESSION_FILE_NAME: str`, `paths.PathOutsideMountError(Exception)`, `paths.resolve_within(mount_root: Path, relative: str) -> Path`.

- [ ] **Step 1: Write the failing test for path resolution**

Create `webapp/tests/test_paths.py`:
```python
from pathlib import Path

import pytest

from webapp import paths


def test_resolves_simple_relative_path(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "file.txt").write_text("hi")

    result = paths.resolve_within(tmp_path, "sub/file.txt")

    assert result == (tmp_path / "sub" / "file.txt").resolve()


def test_empty_relative_path_resolves_to_root(tmp_path):
    result = paths.resolve_within(tmp_path, "")
    assert result == tmp_path.resolve()


def test_rejects_dotdot_traversal(tmp_path):
    with pytest.raises(paths.PathOutsideMountError):
        paths.resolve_within(tmp_path, "../outside.txt")


def test_rejects_dotdot_in_middle_of_path(tmp_path):
    with pytest.raises(paths.PathOutsideMountError):
        paths.resolve_within(tmp_path, "sub/../../outside.txt")


def test_rejects_absolute_path(tmp_path):
    with pytest.raises(paths.PathOutsideMountError):
        paths.resolve_within(tmp_path, "/etc/passwd")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest webapp/tests/test_paths.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'webapp.paths'` or similar)

- [ ] **Step 3: Implement `webapp/config.py`**

```python
import os
from pathlib import Path

MOUNTS: dict[str, Path] = {
    "data": Path(os.environ.get("LDEO_DATA_DIR", "/data")),
    "ladcp": Path(os.environ.get("LDEO_LADCP_DIR", "/ladcp_data")),
    "ctd": Path(os.environ.get("LDEO_CTD_DIR", "/ctd_data")),
    "sadcp": Path(os.environ.get("LDEO_SADCP_DIR", "/sadcp_data")),
    "nav": Path(os.environ.get("LDEO_NAV_DIR", "/navigation_data")),
}

SESSION_FILE_NAME = ".cruise_intake_session.json"


def available_mounts() -> dict[str, Path]:
    return {name: path for name, path in MOUNTS.items() if path.is_dir()}
```

- [ ] **Step 4: Implement `webapp/paths.py`**

```python
from pathlib import Path, PurePosixPath


class PathOutsideMountError(Exception):
    pass


def resolve_within(mount_root: Path, relative: str) -> Path:
    if relative in ("", "."):
        candidate_parts: tuple = ()
    else:
        rel = PurePosixPath(relative.replace("\\", "/"))
        if rel.is_absolute() or ".." in rel.parts:
            raise PathOutsideMountError(f"{relative!r} is not a safe relative path")
        candidate_parts = rel.parts

    root = mount_root.resolve()
    candidate = root.joinpath(*candidate_parts).resolve()

    try:
        candidate.relative_to(root)
    except ValueError:
        raise PathOutsideMountError(f"{relative!r} escapes mount root {root}")

    return candidate
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest webapp/tests/test_paths.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: Commit**

```bash
git add webapp/config.py webapp/paths.py webapp/tests/test_paths.py
git commit -m "feat: add mount config and path-traversal-safe path resolution"
```

---

## Task 3: File browser module and API route

**Files:**
- Create: `webapp/file_browser.py`
- Modify: `webapp/main.py`
- Test: `webapp/tests/test_file_browser.py`
- Test: `webapp/tests/test_main_browse_route.py`

**Interfaces:**
- Consumes: `paths.resolve_within` (Task 2), `config.MOUNTS`/`config.available_mounts` (Task 2)
- Produces: `file_browser.DirEntry` (dataclass: `name: str`, `is_dir: bool`, `relative_path: str`), `file_browser.list_directory(mount_root: Path, relative: str = "") -> list[DirEntry]`. Adds `GET /api/mounts` and `GET /api/browse/{mount}` routes to `webapp.main.app`.

- [ ] **Step 1: Write the failing test for `list_directory`**

Create `webapp/tests/test_file_browser.py`:
```python
from webapp import file_browser


def test_lists_files_and_dirs_sorted_dirs_first(tmp_path):
    (tmp_path / "zeta.txt").write_text("a")
    (tmp_path / "alpha_dir").mkdir()
    (tmp_path / "beta.txt").write_text("b")

    entries = file_browser.list_directory(tmp_path)

    names = [e.name for e in entries]
    assert names == ["alpha_dir", "beta.txt", "zeta.txt"]
    assert entries[0].is_dir is True
    assert entries[1].is_dir is False


def test_relative_path_is_reported_for_nested_entries(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "file.txt").write_text("a")

    entries = file_browser.list_directory(tmp_path, "sub")

    assert entries[0].relative_path == "sub/file.txt"


def test_raises_for_traversal_attempt(tmp_path):
    from webapp import paths

    try:
        file_browser.list_directory(tmp_path, "../")
        assert False, "expected PathOutsideMountError"
    except paths.PathOutsideMountError:
        pass
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest webapp/tests/test_file_browser.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'webapp.file_browser'`)

- [ ] **Step 3: Implement `webapp/file_browser.py`**

```python
from dataclasses import dataclass
from pathlib import Path

from webapp import paths


@dataclass
class DirEntry:
    name: str
    is_dir: bool
    relative_path: str


def list_directory(mount_root: Path, relative: str = "") -> list[DirEntry]:
    target = paths.resolve_within(mount_root, relative)
    if not target.is_dir():
        raise NotADirectoryError(f"{target} is not a directory")

    prefix = relative.strip("/")
    entries = []
    for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        rel = f"{prefix}/{child.name}" if prefix else child.name
        entries.append(DirEntry(name=child.name, is_dir=child.is_dir(), relative_path=rel))
    return entries
```

- [ ] **Step 4: Run to verify the browser tests pass**

Run: `python -m pytest webapp/tests/test_file_browser.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Write the failing test for the API routes**

Create `webapp/tests/test_main_browse_route.py`:
```python
from fastapi.testclient import TestClient

from webapp import config, main


def test_mounts_endpoint_lists_only_existing_dirs(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "ctd", tmp_path)
    monkeypatch.setitem(config.MOUNTS, "sadcp", tmp_path / "does-not-exist")

    client = TestClient(main.app)
    response = client.get("/api/mounts")

    assert response.status_code == 200
    assert "ctd" in response.json()["mounts"]
    assert "sadcp" not in response.json()["mounts"]


def test_browse_endpoint_lists_directory_contents(tmp_path, monkeypatch):
    (tmp_path / "cast1.cnv").write_text("data")
    monkeypatch.setitem(config.MOUNTS, "ctd", tmp_path)

    client = TestClient(main.app)
    response = client.get("/api/browse/ctd")

    assert response.status_code == 200
    names = [e["name"] for e in response.json()["entries"]]
    assert names == ["cast1.cnv"]


def test_browse_endpoint_rejects_unknown_mount():
    client = TestClient(main.app)
    response = client.get("/api/browse/nope")
    assert response.status_code == 404


def test_browse_endpoint_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "ctd", tmp_path)

    client = TestClient(main.app)
    response = client.get("/api/browse/ctd", params={"path": "../../etc"})

    assert response.status_code == 400
```

- [ ] **Step 6: Run to verify it fails**

Run: `python -m pytest webapp/tests/test_main_browse_route.py -v`
Expected: FAIL (404 on `/api/mounts`, route doesn't exist yet)

- [ ] **Step 7: Add the routes to `webapp/main.py`**

Modify `webapp/main.py` to:
```python
from fastapi import FastAPI, HTTPException

from webapp import config, file_browser, paths

app = FastAPI(title="LDEO_IX Cruise/Cast Intake")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/mounts")
def list_mounts():
    return {"mounts": sorted(config.available_mounts().keys())}


@app.get("/api/browse/{mount}")
def browse(mount: str, path: str = ""):
    mount_root = config.MOUNTS.get(mount)
    if mount_root is None or not mount_root.is_dir():
        raise HTTPException(status_code=404, detail=f"mount {mount!r} not available")

    try:
        entries = file_browser.list_directory(mount_root, path)
    except paths.PathOutsideMountError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except NotADirectoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "entries": [
            {"name": e.name, "is_dir": e.is_dir, "relative_path": e.relative_path}
            for e in entries
        ]
    }
```

- [ ] **Step 8: Run to verify it passes**

Run: `python -m pytest webapp/tests/test_main_browse_route.py -v`
Expected: PASS (4 passed)

- [ ] **Step 9: Commit**

```bash
git add webapp/file_browser.py webapp/main.py webapp/tests/test_file_browser.py webapp/tests/test_main_browse_route.py
git commit -m "feat: add mount-scoped file browser API"
```

---

## Task 4: CTD/nav delimited file structural sniffer and preview

**Files:**
- Create: `webapp/delimited_parser.py`
- Modify: `webapp/main.py`
- Test: `webapp/tests/test_delimited_parser.py`

**Interfaces:**
- Consumes: nothing new (pure file parsing)
- Produces: `delimited_parser.DelimitedPreview` (dataclass: `header_lines: int`, `fields_per_line: int`, `preview_rows: list[list[str]]`), `delimited_parser.sniff_and_preview(file_path: Path, max_rows: int = 10) -> DelimitedPreview`. Adds `GET /api/preview/{mount}` route.

- [ ] **Step 1: Write the failing test**

Create `webapp/tests/test_delimited_parser.py`:
```python
from webapp import delimited_parser


def test_sniffs_zero_header_lines_and_field_count(tmp_path):
    f = tmp_path / "003.2Hz"
    f.write_text(
        "1523980583.0 5.234 12.10 34.90 0 0 0 0 0 -15.498335 -150.196990\n"
        "1523980584.0 5.240 12.11 34.91 0 0 0 0 0 -15.498336 -150.196991\n"
    )

    preview = delimited_parser.sniff_and_preview(f)

    assert preview.header_lines == 0
    assert preview.fields_per_line == 11
    assert preview.preview_rows[0][0] == "1523980583.0"
    assert len(preview.preview_rows) == 2


def test_sniffs_header_lines_before_numeric_data(tmp_path):
    f = tmp_path / "with_header.txt"
    f.write_text(
        "% CTD decimated series\n"
        "% generated 2015-04-11\n"
        "1.0 2.0 3.0\n"
        "4.0 5.0 6.0\n"
    )

    preview = delimited_parser.sniff_and_preview(f)

    assert preview.header_lines == 2
    assert preview.fields_per_line == 3


def test_limits_preview_rows_to_max_rows(tmp_path):
    f = tmp_path / "long.txt"
    f.write_text("\n".join(f"{i}.0 {i}.1" for i in range(20)) + "\n")

    preview = delimited_parser.sniff_and_preview(f, max_rows=5)

    assert len(preview.preview_rows) == 5


def test_empty_file_returns_zero_fields(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("")

    preview = delimited_parser.sniff_and_preview(f)

    assert preview.fields_per_line == 0
    assert preview.preview_rows == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest webapp/tests/test_delimited_parser.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implement `webapp/delimited_parser.py`**

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DelimitedPreview:
    header_lines: int
    fields_per_line: int
    preview_rows: list


def sniff_and_preview(file_path: Path, max_rows: int = 10) -> DelimitedPreview:
    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
        lines = [line.rstrip("\n") for line in fh if line.strip() != ""]

    header_lines = 0
    for line in lines:
        tokens = line.strip().split()
        if tokens and all(_is_number(tok) for tok in tokens):
            break
        header_lines += 1

    data_lines = lines[header_lines:]
    fields_per_line = len(data_lines[0].split()) if data_lines else 0
    preview_rows = [line.split() for line in data_lines[:max_rows]]

    return DelimitedPreview(
        header_lines=header_lines,
        fields_per_line=fields_per_line,
        preview_rows=preview_rows,
    )


def _is_number(token: str) -> bool:
    try:
        float(token)
        return True
    except ValueError:
        return False
```

Note: blank lines are dropped before counting (`if line.strip() != ""`), matching how `loadctd.m`/`loadnav.m` treat `header_lines` as a count of leading non-data lines, not raw file lines including blanks.

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest webapp/tests/test_delimited_parser.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Add the preview API route**

Modify `webapp/main.py` — add import and route:
```python
from webapp import config, delimited_parser, file_browser, paths
```
```python
@app.get("/api/preview/{mount}")
def preview_file(mount: str, path: str):
    mount_root = config.MOUNTS.get(mount)
    if mount_root is None or not mount_root.is_dir():
        raise HTTPException(status_code=404, detail=f"mount {mount!r} not available")

    try:
        resolved = paths.resolve_within(mount_root, path)
    except paths.PathOutsideMountError:
        raise HTTPException(status_code=400, detail="path is outside the allowed directory")

    if not resolved.is_file():
        raise HTTPException(status_code=404, detail=f"{path!r} is not a file")

    preview = delimited_parser.sniff_and_preview(resolved)
    return {
        "header_lines": preview.header_lines,
        "fields_per_line": preview.fields_per_line,
        "preview_rows": preview.preview_rows,
    }
```

- [ ] **Step 6: Write and run a route-level test**

Add to `webapp/tests/test_main_browse_route.py`:
```python
def test_preview_endpoint_returns_sniffed_structure(tmp_path, monkeypatch):
    (tmp_path / "cast1.cnv").write_text("1.0 2.0 3.0\n4.0 5.0 6.0\n")
    monkeypatch.setitem(config.MOUNTS, "ctd", tmp_path)

    client = TestClient(main.app)
    response = client.get("/api/preview/ctd", params={"path": "cast1.cnv"})

    assert response.status_code == 200
    body = response.json()
    assert body["header_lines"] == 0
    assert body["fields_per_line"] == 3
```

Run: `python -m pytest webapp/tests/test_main_browse_route.py -v`
Expected: PASS (5 passed)

- [ ] **Step 7: Commit**

```bash
git add webapp/delimited_parser.py webapp/main.py webapp/tests/test_delimited_parser.py webapp/tests/test_main_browse_route.py
git commit -m "feat: add CTD/nav structural sniffer and preview API"
```

---

## Task 5: LADCP raw file scan and down/up pairing

**Files:**
- Create: `webapp/ladcp_scan.py`
- Modify: `webapp/main.py`
- Test: `webapp/tests/test_ladcp_scan.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `ladcp_scan.LadcpCastFiles` (dataclass: `station: str`, `down: str | None`, `up: str | None`), `ladcp_scan.scan_ladcp_directory(mount_root: Path) -> list[LadcpCastFiles]`. Adds `GET /api/ladcp/scan` route.

- [ ] **Step 1: Write the failing test**

Create `webapp/tests/test_ladcp_scan.py`:
```python
from webapp import ladcp_scan


def test_pairs_down_and_up_files_by_station(tmp_path):
    (tmp_path / "003DL000.000").write_text("")
    (tmp_path / "003UL000.000").write_text("")
    (tmp_path / "004DL000.000").write_text("")

    results = ladcp_scan.scan_ladcp_directory(tmp_path)

    by_station = {r.station: r for r in results}
    assert by_station["003"].down == "003DL000.000"
    assert by_station["003"].up == "003UL000.000"
    assert by_station["004"].down == "004DL000.000"
    assert by_station["004"].up is None


def test_ignores_files_that_dont_match_the_convention(tmp_path):
    (tmp_path / "readme.txt").write_text("")
    (tmp_path / "003DL000.000").write_text("")

    results = ladcp_scan.scan_ladcp_directory(tmp_path)

    assert len(results) == 1
    assert results[0].station == "003"


def test_results_sorted_by_station(tmp_path):
    (tmp_path / "010DL000.000").write_text("")
    (tmp_path / "002DL000.000").write_text("")

    results = ladcp_scan.scan_ladcp_directory(tmp_path)

    assert [r.station for r in results] == ["002", "010"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest webapp/tests/test_ladcp_scan.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implement `webapp/ladcp_scan.py`**

```python
import re
from dataclasses import dataclass
from pathlib import Path

_FILENAME_RE = re.compile(r"^(?P<station>\d+)(?P<dir>[DU])L\d+\.\d+$", re.IGNORECASE)


@dataclass
class LadcpCastFiles:
    station: str
    down: str = None
    up: str = None


def scan_ladcp_directory(mount_root: Path) -> list:
    by_station: dict = {}
    for entry in sorted(mount_root.iterdir()):
        if not entry.is_file():
            continue
        match = _FILENAME_RE.match(entry.name)
        if not match:
            continue
        station = match.group("station")
        direction = match.group("dir").upper()
        slot = by_station.setdefault(station, {"down": None, "up": None})
        if direction == "D":
            slot["down"] = entry.name
        else:
            slot["up"] = entry.name

    return [
        LadcpCastFiles(station=station, down=files["down"], up=files["up"])
        for station, files in sorted(by_station.items())
    ]
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest webapp/tests/test_ladcp_scan.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Add the scan API route**

Modify `webapp/main.py` — add import and route:
```python
from webapp import config, delimited_parser, file_browser, ladcp_scan, paths
```
```python
@app.get("/api/ladcp/scan")
def scan_ladcp():
    mount_root = config.MOUNTS.get("ladcp")
    if mount_root is None or not mount_root.is_dir():
        raise HTTPException(status_code=404, detail="ladcp mount not available")

    results = ladcp_scan.scan_ladcp_directory(mount_root)
    return {
        "casts": [
            {"station": r.station, "down": r.down, "up": r.up} for r in results
        ]
    }
```

- [ ] **Step 6: Write and run a route-level test**

Add to `webapp/tests/test_main_browse_route.py`:
```python
def test_ladcp_scan_endpoint(tmp_path, monkeypatch):
    (tmp_path / "003DL000.000").write_text("")
    (tmp_path / "003UL000.000").write_text("")
    monkeypatch.setitem(config.MOUNTS, "ladcp", tmp_path)

    client = TestClient(main.app)
    response = client.get("/api/ladcp/scan")

    assert response.status_code == 200
    casts = response.json()["casts"]
    assert casts == [{"station": "003", "down": "003DL000.000", "up": "003UL000.000"}]
```

Run: `python -m pytest webapp/tests/test_main_browse_route.py -v`
Expected: PASS (6 passed)

- [ ] **Step 7: Commit**

```bash
git add webapp/ladcp_scan.py webapp/main.py webapp/tests/test_ladcp_scan.py webapp/tests/test_main_browse_route.py
git commit -m "feat: add LADCP raw file scan and down/up pairing"
```

---

## Task 6: Prior-cast NetCDF attribute reader

**Files:**
- Create: `webapp/netcdf_reader.py`
- Test: `webapp/tests/test_netcdf_reader.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `netcdf_reader.read_global_attributes(nc_path: Path) -> dict`

- [ ] **Step 1: Write the failing test**

Create `webapp/tests/test_netcdf_reader.py`:
```python
from scipy.io import netcdf_file

from webapp import netcdf_reader


def _write_fixture_nc(path):
    nc = netcdf_file(path, "w")
    nc.createDimension("one", 1)
    var = nc.createVariable("placeholder", "f8", ("one",))
    var[:] = 0.0
    nc.lat = -15.498335
    nc.lon = -150.19699
    nc.drot = 12.318441
    nc.name = "003"
    nc.close()


def test_reads_global_attributes_written_by_scipy(tmp_path):
    nc_path = tmp_path / "003.nc"
    _write_fixture_nc(nc_path)

    attrs = netcdf_reader.read_global_attributes(nc_path)

    assert attrs["lat"] == -15.498335
    assert attrs["lon"] == -150.19699
    assert attrs["drot"] == 12.318441
    assert attrs["name"] == "003"


def test_missing_file_raises_file_not_found_error(tmp_path):
    import pytest

    with pytest.raises(FileNotFoundError):
        netcdf_reader.read_global_attributes(tmp_path / "missing.nc")
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest webapp/tests/test_netcdf_reader.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implement `webapp/netcdf_reader.py`**

```python
from pathlib import Path
from typing import Any

from scipy.io import netcdf_file


def read_global_attributes(nc_path: Path) -> dict:
    if not Path(nc_path).is_file():
        raise FileNotFoundError(str(nc_path))

    attrs: dict = {}
    with netcdf_file(str(nc_path), "r", mmap=False) as nc:
        # scipy's netcdf_file has no public "list global attributes" API;
        # it stores them in this internal dict (documented workaround used
        # widely since scipy doesn't expose a first-class accessor for it).
        for name, value in nc._attributes.items():
            if isinstance(value, bytes):
                value = value.decode("utf-8", errors="replace")
            attrs[name] = value
    return attrs
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest webapp/tests/test_netcdf_reader.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add webapp/netcdf_reader.py webapp/tests/test_netcdf_reader.py
git commit -m "feat: add prior-cast netCDF global attribute reader"
```

**Note for the implementer:** this task's test proves the reader round-trips attributes written by the same library (`scipy.io.netcdf_file`), which is the best available verification without a real LDEO_IX output file in this repo. Before relying on "clone from netCDF" against real cruise data (Task 10), confirm a real `process_cast` output `.nc` is actually classic NetCDF3 (`file <path>.nc` or `ncdump -h <path>.nc` — classic format reports as "NetCDF Data Format data"; if it reports HDF5, swap this module to use `netCDF4` or `h5netcdf` instead, keeping the same `read_global_attributes` signature so nothing else changes).

---

## Task 7: Cast/session models and sidecar persistence

**Files:**
- Create: `webapp/models.py`
- Create: `webapp/session_store.py`
- Test: `webapp/tests/test_session_store.py`

**Interfaces:**
- Consumes: `config.MOUNTS["data"]`, `config.SESSION_FILE_NAME` (Task 2)
- Produces: `models.CastEntry` (pydantic `BaseModel`), `models.CruiseSession` (pydantic `BaseModel`, field `casts: list[CastEntry]`, field `cruise_id: str`), `session_store.load_session() -> CruiseSession`, `session_store.save_session(session: CruiseSession) -> None`, `session_store.session_path() -> Path`.

- [ ] **Step 1: Write the failing test**

Create `webapp/tests/test_session_store.py`:
```python
from webapp import config, session_store
from webapp.models import CastEntry, CruiseSession


def test_load_session_returns_empty_session_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)

    session = session_store.load_session()

    assert session.cruise_id == ""
    assert session.casts == []


def test_save_then_load_round_trips_cast_data(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)

    session = CruiseSession(cruise_id="P16N", casts=[
        CastEntry(cast_name="003", lat=-15.498335, lon=-150.19699)
    ])
    session_store.save_session(session)

    loaded = session_store.load_session()

    assert loaded.cruise_id == "P16N"
    assert len(loaded.casts) == 1
    assert loaded.casts[0].cast_name == "003"
    assert loaded.casts[0].lat == -15.498335


def test_session_file_written_at_expected_path(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)

    session_store.save_session(CruiseSession())

    assert session_store.session_path() == tmp_path / ".cruise_intake_session.json"
    assert session_store.session_path().is_file()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest webapp/tests/test_session_store.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implement `webapp/models.py`**

```python
import uuid
from typing import Optional

from pydantic import BaseModel, Field


class CastEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    cast_name: str = ""

    ladcp_station: Optional[int] = None
    ladcp_cast: Optional[int] = None
    ladcpdo: str = ""
    ladcpup: str = ""

    ctd: str = ""
    ctd_header_lines: Optional[int] = None
    ctd_fields_per_line: Optional[int] = None
    ctd_time_field: Optional[int] = None
    ctd_pressure_field: Optional[int] = None
    ctd_temperature_field: Optional[int] = None
    ctd_salinity_field: Optional[int] = None
    ctd_badvals: float = -9e99
    ctd_time_base: int = 0

    nav: str = ""
    nav_header_lines: Optional[int] = None
    nav_fields_per_line: Optional[int] = None
    nav_time_field: Optional[int] = None
    nav_lat_field: Optional[int] = None
    nav_lon_field: Optional[int] = None
    nav_time_base: int = 0
    nav_error: float = 30

    sadcp: str = ""

    drot: Optional[float] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    time_start: Optional[list] = None
    time_end: Optional[list] = None

    btrk_mode: int = 3
    btrk_used: int = 1

    checkpoints_file: str = ""
    res_file: str = ""
    checkpoints_steps: str = "1:16"


class CruiseSession(BaseModel):
    cruise_id: str = ""
    casts: list = Field(default_factory=list)
```

- [ ] **Step 4: Implement `webapp/session_store.py`**

```python
from pathlib import Path

from webapp import config
from webapp.models import CruiseSession


def session_path() -> Path:
    return config.MOUNTS["data"] / config.SESSION_FILE_NAME


def load_session() -> CruiseSession:
    path = session_path()
    if not path.is_file():
        return CruiseSession()
    return CruiseSession.model_validate_json(path.read_text(encoding="utf-8"))


def save_session(session: CruiseSession) -> None:
    path = session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(session.model_dump_json(indent=2), encoding="utf-8")
```

- [ ] **Step 5: Run to verify it passes**

Run: `python -m pytest webapp/tests/test_session_store.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add webapp/models.py webapp/session_store.py webapp/tests/test_session_store.py
git commit -m "feat: add cast/session models and sidecar JSON persistence"
```

---

## Task 8: `set_cast_params.m` template generator

**Files:**
- Create: `webapp/template_gen.py`
- Test: `webapp/tests/test_template_gen.py`

**Interfaces:**
- Consumes: `models.CastEntry`, `models.CruiseSession` (Task 7)
- Produces: `template_gen.render_set_cast_params(session: CruiseSession) -> str`

- [ ] **Step 1: Write the failing test**

Create `webapp/tests/test_template_gen.py`:
```python
from webapp import template_gen
from webapp.models import CastEntry, CruiseSession


def _p16n_cast003():
    return CastEntry(
        cast_name="003",
        ladcp_station=3,
        ladcp_cast=1,
        ladcpdo="data/raw/003DL000.000",
        ladcpup="data/raw/003UL000.000",
        ctd="data/CTD/2Hz/003.2Hz",
        nav="data/CTD/2Hz/003.2Hz",
        ctd_header_lines=0,
        ctd_fields_per_line=11,
        ctd_time_field=1,
        ctd_pressure_field=2,
        ctd_temperature_field=3,
        ctd_salinity_field=4,
        ctd_badvals=-999,
        ctd_time_base=0,
        nav_header_lines=0,
        nav_fields_per_line=11,
        nav_time_field=1,
        nav_lat_field=10,
        nav_lon_field=11,
        nav_time_base=0,
        nav_error=30,
        drot=12.318441,
        lat=-15.498335,
        lon=-150.19699,
        time_start=[2015, 4, 11, 17, 36, 23.312975],
        time_end=[2015, 4, 11, 21, 9, 42.220459],
        btrk_mode=3,
        btrk_used=1,
        checkpoints_file="checkpoints/003",
        res_file="V7/003",
        checkpoints_steps="1:16",
    )


def test_renders_switch_case_with_one_cast_per_station():
    session = CruiseSession(cruise_id="P16N", casts=[_p16n_cast003()])

    output = template_gen.render_set_cast_params(session)

    assert "cruise_id = 'P16N';" in output
    assert "switch stn" in output
    assert "case 3" in output
    assert "f.ladcpdo = 'data/raw/003DL000.000';" in output
    assert "f.ladcpup = 'data/raw/003UL000.000';" in output
    assert "p.lat = -15.498335;" in output
    assert "p.time_start = [2015 4 11 17 36 23.312975];" in output
    assert "p.checkpoints = 1:16;" in output
    assert output.strip().endswith("end")


def test_renders_multiple_casts_as_separate_cases():
    cast3 = _p16n_cast003()
    cast4 = _p16n_cast003()
    cast4.ladcp_station = 4
    cast4.cast_name = "004"

    session = CruiseSession(cruise_id="P16N", casts=[cast3, cast4])

    output = template_gen.render_set_cast_params(session)

    assert "case 3" in output
    assert "case 4" in output


def test_omits_sadcp_line_when_unset():
    cast = _p16n_cast003()
    session = CruiseSession(casts=[cast])

    output = template_gen.render_set_cast_params(session)

    assert "f.sadcp" not in output


def test_includes_sadcp_line_when_set():
    cast = _p16n_cast003()
    cast.sadcp = "data/sadcp/003.mat"
    session = CruiseSession(casts=[cast])

    output = template_gen.render_set_cast_params(session)

    assert "f.sadcp = 'data/sadcp/003.mat';" in output


def test_quotes_are_escaped_in_string_fields():
    cast = _p16n_cast003()
    cast.cast_name = "o'brien"
    session = CruiseSession(casts=[cast])

    output = template_gen.render_set_cast_params(session)

    assert "p.name = 'o''brien';" in output
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest webapp/tests/test_template_gen.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implement `webapp/template_gen.py`**

```python
from webapp.models import CastEntry, CruiseSession


def render_set_cast_params(session: CruiseSession) -> str:
    lines = [f"cruise_id = '{_escape(session.cruise_id)}';", "p.cruise_id = cruise_id;", "", "switch stn"]

    for cast in session.casts:
        lines.append(f"  case {cast.ladcp_station}")
        lines.extend(_render_cast_body(cast))
        lines.append("")

    lines.append("end")
    return "\n".join(lines) + "\n"


def _render_cast_body(cast: CastEntry) -> list:
    body = []

    def add(field, value):
        body.append(f"    {field} = {value};")

    add("f.ladcpdo", _quote(cast.ladcpdo))
    add("f.ladcpup", _quote(cast.ladcpup))
    add("p.ladcp_station", cast.ladcp_station)
    add("p.ladcp_cast", cast.ladcp_cast)
    add("p.name", _quote(cast.cast_name))

    add("f.ctd", _quote(cast.ctd))
    add("f.nav", _quote(cast.nav))
    add("f.ctd_header_lines", cast.ctd_header_lines)
    add("f.ctd_fields_per_line", cast.ctd_fields_per_line)
    add("f.ctd_time_field", cast.ctd_time_field)
    add("f.ctd_pressure_field", cast.ctd_pressure_field)
    add("f.ctd_temperature_field", cast.ctd_temperature_field)
    add("f.ctd_salinity_field", cast.ctd_salinity_field)
    add("f.ctd_badvals", cast.ctd_badvals)
    add("f.ctd_time_base", cast.ctd_time_base)
    add("f.nav_header_lines", cast.nav_header_lines)
    add("f.nav_fields_per_line", cast.nav_fields_per_line)
    add("f.nav_time_field", cast.nav_time_field)
    add("f.nav_lat_field", cast.nav_lat_field)
    add("f.nav_lon_field", cast.nav_lon_field)
    add("f.nav_time_base", cast.nav_time_base)
    add("p.nav_time_base", cast.nav_time_base)
    add("p.nav_error", cast.nav_error)

    if cast.sadcp:
        add("f.sadcp", _quote(cast.sadcp))

    add("p.drot", cast.drot)
    add("p.lat", cast.lat)
    add("p.lon", cast.lon)
    add("p.time_start", _matlab_vector(cast.time_start))
    add("p.time_end", _matlab_vector(cast.time_end))

    add("p.btrk_mode", cast.btrk_mode)
    add("p.btrk_used", cast.btrk_used)

    add("f.checkpoints", _quote(cast.checkpoints_file))
    add("f.res", _quote(cast.res_file))
    add("p.checkpoints", cast.checkpoints_steps)

    return body


def _quote(value: str) -> str:
    return "'" + (value or "").replace("'", "''") + "'"


def _escape(value: str) -> str:
    return (value or "").replace("'", "''")


def _matlab_vector(values) -> str:
    if not values:
        return "[]"
    return "[" + " ".join(str(v) for v in values) + "]"
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest webapp/tests/test_template_gen.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add webapp/template_gen.py webapp/tests/test_template_gen.py
git commit -m "feat: add set_cast_params.m template generator"
```

---

## Task 9: Validation (required fields + referenced-file warnings)

**Files:**
- Create: `webapp/validation.py`
- Test: `webapp/tests/test_validation.py`

**Interfaces:**
- Consumes: `models.CruiseSession`, `models.CastEntry` (Task 7), `config.MOUNTS` (Task 2)
- Produces: `validation.ValidationResult` (dataclass: `errors: dict[str, list[str]]`, `warnings: dict[str, list[str]]`, property `is_valid: bool`), `validation.validate_session(session: CruiseSession) -> ValidationResult`

- [ ] **Step 1: Write the failing test**

Create `webapp/tests/test_validation.py`:
```python
from webapp import config, validation
from webapp.models import CastEntry, CruiseSession


def _valid_cast(**overrides):
    defaults = dict(
        ladcpdo="003DL000.000",
        ladcpup="003UL000.000",
        ladcp_station=3,
        ladcp_cast=1,
        lat=-15.5,
        lon=-150.2,
        time_start=[2015, 4, 11, 17, 36, 23.0],
        time_end=[2015, 4, 11, 21, 9, 42.0],
    )
    defaults.update(overrides)
    return CastEntry(**defaults)


def test_valid_session_has_no_errors():
    session = CruiseSession(casts=[_valid_cast()])

    result = validation.validate_session(session)

    assert result.is_valid is True
    assert result.errors == {}


def test_missing_required_field_produces_error():
    cast = _valid_cast(lat=None)
    session = CruiseSession(casts=[cast])

    result = validation.validate_session(session)

    assert result.is_valid is False
    assert "lat is required" in result.errors[cast.id]


def test_missing_referenced_file_produces_warning_not_error(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "ladcp", tmp_path)
    cast = _valid_cast(ladcpdo="does-not-exist.000")
    session = CruiseSession(casts=[cast])

    result = validation.validate_session(session)

    assert result.is_valid is True
    assert "does-not-exist.000 not found under ladcp mount" in result.warnings[cast.id]


def test_existing_referenced_file_produces_no_warning(tmp_path, monkeypatch):
    (tmp_path / "003DL000.000").write_text("")
    (tmp_path / "003UL000.000").write_text("")
    monkeypatch.setitem(config.MOUNTS, "ladcp", tmp_path)
    cast = _valid_cast()
    session = CruiseSession(casts=[cast])

    result = validation.validate_session(session)

    assert cast.id not in result.warnings


def test_traversal_attempt_produces_generic_warning_not_a_bypass(tmp_path, monkeypatch):
    mount = tmp_path / "mount"
    mount.mkdir()
    (tmp_path / "secret.txt").write_text("outside the mount")
    monkeypatch.setitem(config.MOUNTS, "ladcp", mount)
    cast = _valid_cast(ladcpdo="../secret.txt")
    session = CruiseSession(casts=[cast])

    result = validation.validate_session(session)

    assert result.is_valid is True
    assert "../secret.txt not found under ladcp mount" in result.warnings[cast.id]
```

(The first draft of this test used `ladcpdo="../../../../etc/passwd"` under a bare `tmp_path` mount — a reviewer correctly flagged that as platform-fragile: it only proves anything if the traversal happens to land exactly on `/etc/passwd`, which doesn't hold on Windows, this project's actual dev platform. The sentinel-file version above is deterministic on any OS.)

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest webapp/tests/test_validation.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implement `webapp/validation.py`**

```python
from dataclasses import dataclass, field

from webapp import config, paths
from webapp.models import CruiseSession

REQUIRED_FIELDS = [
    "ladcpdo", "ladcpup", "ladcp_station", "ladcp_cast",
    "lat", "lon", "time_start", "time_end",
]

_FILE_FIELDS = [
    ("ladcp", "ladcpdo"),
    ("ladcp", "ladcpup"),
    ("ctd", "ctd"),
    ("nav", "nav"),
    ("sadcp", "sadcp"),
]


@dataclass
class ValidationResult:
    errors: dict = field(default_factory=dict)
    warnings: dict = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return not any(self.errors.values())


def validate_session(session: CruiseSession) -> ValidationResult:
    result = ValidationResult()

    for cast in session.casts:
        cast_errors = [
            f"{field_name} is required"
            for field_name in REQUIRED_FIELDS
            if not getattr(cast, field_name)
        ]
        if cast_errors:
            result.errors[cast.id] = cast_errors

        cast_warnings = []
        for mount_name, field_name in _FILE_FIELDS:
            relative = getattr(cast, field_name)
            if not relative:
                continue
            mount_root = config.MOUNTS.get(mount_name)
            if mount_root is None:
                cast_warnings.append(f"{relative} not found under {mount_name} mount")
                continue
            try:
                resolved = paths.resolve_within(mount_root, relative)
            except paths.PathOutsideMountError:
                cast_warnings.append(f"{relative} not found under {mount_name} mount")
                continue
            if not resolved.is_file():
                cast_warnings.append(f"{relative} not found under {mount_name} mount")
        if cast_warnings:
            result.warnings[cast.id] = cast_warnings

    return result
```

**Security note:** this MUST route every candidate path through `paths.resolve_within` before calling `.is_file()` — a cast's file fields (`ladcpdo`, `ctd`, `nav`, etc.) are user-editable strings, and checking `(mount_root / relative).is_file()` directly (without resolving and bounds-checking first) turns this validation step into a path-traversal file-existence oracle: a crafted value like `../../../../etc/passwd` would let a caller learn whether an arbitrary host file exists via the presence/absence of a warning. A traversal attempt is reported with the same generic "not found under mount" warning as a genuinely missing file — it must not surface a different message that would let a caller distinguish "outside the mount" from "inside the mount but missing" (that distinction is itself a smaller oracle).

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest webapp/tests/test_validation.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add webapp/validation.py webapp/tests/test_validation.py
git commit -m "feat: add cast session validation (required fields, file warnings)"
```

---

## Task 10: Cast CRUD API (create, update, delete, clone, clone-from-netcdf)

**Files:**
- Create: `webapp/api.py`
- Modify: `webapp/main.py`
- Test: `webapp/tests/test_api_casts.py`

**Interfaces:**
- Consumes: `models.CastEntry`/`CruiseSession`, `session_store.load_session`/`save_session` (Task 7), `netcdf_reader.read_global_attributes` (Task 6)
- Produces: FastAPI `APIRouter` at `webapp.api.router`, mounted under `/api/session` in `main.py`. Routes: `GET /api/session`, `POST /api/session/casts`, `PUT /api/session/casts/{id}`, `DELETE /api/session/casts/{id}`, `POST /api/session/casts/{id}/clone`, `POST /api/session/casts/from-netcdf`.

- [ ] **Step 1: Write the failing test**

Create `webapp/tests/test_api_casts.py`:
```python
from fastapi.testclient import TestClient
from scipy.io import netcdf_file

from webapp import config, main


def test_get_session_starts_empty(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)

    client = TestClient(main.app)
    response = client.get("/api/session")

    assert response.status_code == 200
    assert response.json()["casts"] == []


def test_create_cast_persists_to_session(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)
    client = TestClient(main.app)

    response = client.post("/api/session/casts", json={"cast_name": "003", "ladcp_station": 3})

    assert response.status_code == 201
    body = response.json()
    assert body["cast_name"] == "003"
    assert body["checkpoints_file"] == "checkpoints/003"
    assert body["res_file"] == "V7/003"

    session = client.get("/api/session").json()
    assert len(session["casts"]) == 1


def test_update_cast_changes_fields(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)
    client = TestClient(main.app)
    created = client.post("/api/session/casts", json={"cast_name": "003"}).json()

    response = client.put(f"/api/session/casts/{created['id']}", json={"lat": -15.5})

    assert response.status_code == 200
    assert response.json()["lat"] == -15.5


def test_delete_cast_removes_it(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)
    client = TestClient(main.app)
    created = client.post("/api/session/casts", json={"cast_name": "003"}).json()

    response = client.delete(f"/api/session/casts/{created['id']}")

    assert response.status_code == 204
    assert client.get("/api/session").json()["casts"] == []


def test_clone_cast_creates_copy_with_new_id(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)
    client = TestClient(main.app)
    created = client.post("/api/session/casts", json={"cast_name": "003", "lat": -15.5}).json()

    response = client.post(f"/api/session/casts/{created['id']}/clone")

    assert response.status_code == 201
    clone = response.json()
    assert clone["id"] != created["id"]
    assert clone["lat"] == -15.5


def test_clone_from_netcdf_prefills_known_fields(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)
    nc_path = tmp_path / "003.nc"
    nc = netcdf_file(str(nc_path), "w")
    nc.createDimension("one", 1)
    var = nc.createVariable("placeholder", "f8", ("one",))
    var[:] = 0.0
    nc.lat = -15.498335
    nc.lon = -150.19699
    nc.close()
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)

    client = TestClient(main.app)
    response = client.post("/api/session/casts/from-netcdf", params={"path": "003.nc"})

    assert response.status_code == 201
    body = response.json()
    assert body["lat"] == -15.498335
    assert body["lon"] == -150.19699
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest webapp/tests/test_api_casts.py -v`
Expected: FAIL (404s — routes don't exist)

- [ ] **Step 3: Implement `webapp/api.py`**

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from webapp import config, netcdf_reader, paths, session_store
from webapp.models import CastEntry

router = APIRouter()


class CastPatch(BaseModel):
    model_config = {"extra": "allow"}


@router.get("/session")
def get_session():
    return session_store.load_session()


@router.post("/session/casts", status_code=201)
def create_cast(patch: CastPatch):
    session = session_store.load_session()
    data = patch.model_dump(exclude_unset=True)
    cast = CastEntry(**data)

    if not cast.checkpoints_file and cast.cast_name:
        cast.checkpoints_file = f"checkpoints/{cast.cast_name}"
    if not cast.res_file and cast.cast_name:
        cast.res_file = f"V7/{cast.cast_name}"

    session.casts.append(cast)
    session_store.save_session(session)
    return cast


@router.put("/session/casts/{cast_id}")
def update_cast(cast_id: str, patch: CastPatch):
    session = session_store.load_session()
    for i, cast in enumerate(session.casts):
        if cast.id == cast_id:
            updated = cast.model_copy(update=patch.model_dump(exclude_unset=True))
            session.casts[i] = updated
            session_store.save_session(session)
            return updated
    raise HTTPException(status_code=404, detail=f"cast {cast_id!r} not found")


@router.delete("/session/casts/{cast_id}", status_code=204)
def delete_cast(cast_id: str):
    session = session_store.load_session()
    remaining = [c for c in session.casts if c.id != cast_id]
    if len(remaining) == len(session.casts):
        raise HTTPException(status_code=404, detail=f"cast {cast_id!r} not found")
    session.casts = remaining
    session_store.save_session(session)


@router.post("/session/casts/{cast_id}/clone", status_code=201)
def clone_cast(cast_id: str):
    session = session_store.load_session()
    for cast in session.casts:
        if cast.id == cast_id:
            data = cast.model_dump()
            data.pop("id")
            clone = CastEntry(**data)
            session.casts.append(clone)
            session_store.save_session(session)
            return clone
    raise HTTPException(status_code=404, detail=f"cast {cast_id!r} not found")


@router.post("/session/casts/from-netcdf", status_code=201)
def create_cast_from_netcdf(path: str):
    mount_root = config.MOUNTS.get("data")
    try:
        resolved = paths.resolve_within(mount_root, path)
    except paths.PathOutsideMountError:
        raise HTTPException(status_code=400, detail="path is outside the allowed directory")

    try:
        attrs = netcdf_reader.read_global_attributes(resolved)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"{path!r} not found")

    known_fields = set(CastEntry.model_fields.keys())
    prefill = {k: v for k, v in attrs.items() if k in known_fields}

    session = session_store.load_session()
    cast = CastEntry(**prefill)
    session.casts.append(cast)
    session_store.save_session(session)
    return cast
```

`clone_cast` dumps the original cast's data, drops the `id` key, and re-constructs a `CastEntry` — since `id` is then genuinely omitted from the constructor kwargs, its `default_factory` generates a fresh UUID for the clone.

- [ ] **Step 4: Wire the router into `webapp/main.py`**

Modify `webapp/main.py` — add import and include the router:
```python
from webapp import api, config, delimited_parser, file_browser, ladcp_scan, paths
```
```python
app.include_router(api.router, prefix="/api")
```

- [ ] **Step 5: Run to verify it passes**

Run: `python -m pytest webapp/tests/test_api_casts.py -v`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add webapp/api.py webapp/main.py webapp/tests/test_api_casts.py
git commit -m "feat: add cast CRUD API (create, update, delete, clone, clone-from-netcdf)"
```

---

## Task 11: Generate endpoint (validate, backup, write)

**Files:**
- Modify: `webapp/api.py`
- Test: `webapp/tests/test_api_generate.py`

**Interfaces:**
- Consumes: `validation.validate_session` (Task 9), `template_gen.render_set_cast_params` (Task 8), `session_store.load_session` (Task 7)
- Produces: `POST /api/generate` route on `webapp.api.router`.

- [ ] **Step 1: Write the failing test**

Create `webapp/tests/test_api_generate.py`:
```python
from datetime import datetime

from fastapi.testclient import TestClient

from webapp import config, main


def _valid_cast_payload(**overrides):
    payload = dict(
        cast_name="003",
        ladcpdo="003DL000.000",
        ladcpup="003UL000.000",
        ladcp_station=3,
        ladcp_cast=1,
        lat=-15.5,
        lon=-150.2,
        time_start=[2015, 4, 11, 17, 36, 23.0],
        time_end=[2015, 4, 11, 21, 9, 42.0],
    )
    payload.update(overrides)
    return payload


def test_generate_blocked_when_required_fields_missing(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)
    client = TestClient(main.app)
    client.post("/api/session/casts", json={"cast_name": "003"})

    response = client.post("/api/generate")

    assert response.status_code == 400
    assert "errors" in response.json()
    assert not (tmp_path / "set_cast_params.m").exists()


def test_generate_writes_file_when_valid(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)
    client = TestClient(main.app)
    client.post("/api/session/casts", json=_valid_cast_payload())

    response = client.post("/api/generate")

    assert response.status_code == 200
    written = tmp_path / "set_cast_params.m"
    assert written.is_file()
    assert "case 3" in written.read_text()


def test_generate_backs_up_existing_file(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)
    existing = tmp_path / "set_cast_params.m"
    existing.write_text("% hand-written\n")
    client = TestClient(main.app)
    client.post("/api/session/casts", json=_valid_cast_payload())

    client.post("/api/generate")

    backups = list(tmp_path.glob("set_cast_params.m.bak.*"))
    assert len(backups) == 1
    assert backups[0].read_text() == "% hand-written\n"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest webapp/tests/test_api_generate.py -v`
Expected: FAIL (404 — route doesn't exist)

- [ ] **Step 3: Add the generate route to `webapp/api.py`**

Modify `webapp/api.py` — add imports and route:
```python
from datetime import datetime

from webapp import config, netcdf_reader, paths, session_store, template_gen, validation
from webapp.models import CastEntry
```
```python
@router.post("/generate")
def generate():
    session = session_store.load_session()
    result = validation.validate_session(session)

    if not result.is_valid:
        return _json_error(result)

    output = template_gen.render_set_cast_params(session)
    target = config.MOUNTS["data"] / "set_cast_params.m"

    if target.is_file():
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        backup = target.with_name(f"{target.name}.bak.{timestamp}")
        backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")

    target.write_text(output, encoding="utf-8")

    return {"written_to": str(target), "warnings": result.warnings}


def _json_error(result: validation.ValidationResult):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=400, content={"errors": result.errors, "warnings": result.warnings})
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest webapp/tests/test_api_generate.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the full backend test suite to confirm no regressions**

Run: `python -m pytest webapp/tests -v`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add webapp/api.py webapp/tests/test_api_generate.py
git commit -m "feat: add generate endpoint (validate, backup, write set_cast_params.m)"
```

---

## Task 12: Web UI — cast list, add/edit form, LADCP + CTD/nav pickers

**Files:**
- Create: `webapp/templates/base.html`
- Create: `webapp/templates/index.html`
- Create: `webapp/static/app.js`
- Create: `webapp/static/style.css`
- Modify: `webapp/main.py`

**Interfaces:**
- Consumes: all `/api/*` routes from Tasks 3, 4, 5, 10, 11
- Produces: `GET /` (HTML page), static assets under `/static/`

- [ ] **Step 1: Create the base and index templates**

Create `webapp/templates/base.html`:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{% block title %}LDEO_IX Cruise/Cast Intake{% endblock %}</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <header><h1>Cruise/Cast Intake</h1></header>
  <main>{% block content %}{% endblock %}</main>
  {% block scripts %}{% endblock %}
</body>
</html>
```

Create `webapp/templates/index.html`:
```html
{% extends "base.html" %}
{% block content %}
<section id="cruise-header">
  <label>Cruise ID: <input id="cruise-id" type="text"></label>
</section>

<section id="cast-list">
  <h2>Casts</h2>
  <table id="cast-table">
    <thead>
      <tr><th>Name</th><th>Station</th><th>Lat</th><th>Lon</th><th></th></tr>
    </thead>
    <tbody></tbody>
  </table>
  <button id="add-cast">Add cast</button>
</section>

<section id="cast-editor" hidden>
  <h2>Edit cast</h2>
  <form id="cast-form">
    <fieldset>
      <legend>Raw LADCP files</legend>
      <select id="ladcp-suggestions"></select>
      <button type="button" id="apply-ladcp-suggestion">Use selected pair</button>
      <label>Name <input name="cast_name"></label>
      <label>Station <input name="ladcp_station" type="number"></label>
      <label>Cast <input name="ladcp_cast" type="number"></label>
      <label>Down file <input name="ladcpdo"></label>
      <label>Up file <input name="ladcpup"></label>
    </fieldset>

    <fieldset>
      <legend>CTD</legend>
      <label>File <input name="ctd" id="ctd-path"></label>
      <button type="button" id="preview-ctd">Preview / map columns</button>
      <div id="ctd-preview"></div>
      <label>Header lines <input name="ctd_header_lines" type="number"></label>
      <label>Fields per line <input name="ctd_fields_per_line" type="number"></label>
      <label>Time field <input name="ctd_time_field" type="number"></label>
      <label>Pressure field <input name="ctd_pressure_field" type="number"></label>
      <label>Temperature field <input name="ctd_temperature_field" type="number"></label>
      <label>Salinity field <input name="ctd_salinity_field" type="number"></label>
      <label>Bad value <input name="ctd_badvals" type="number"></label>
    </fieldset>

    <fieldset>
      <legend>Nav</legend>
      <label>File <input name="nav" id="nav-path"></label>
      <button type="button" id="preview-nav">Preview / map columns</button>
      <div id="nav-preview"></div>
      <label>Header lines <input name="nav_header_lines" type="number"></label>
      <label>Fields per line <input name="nav_fields_per_line" type="number"></label>
      <label>Time field <input name="nav_time_field" type="number"></label>
      <label>Lat field <input name="nav_lat_field" type="number"></label>
      <label>Lon field <input name="nav_lon_field" type="number"></label>
    </fieldset>

    <fieldset>
      <legend>Position / time / bottom-tracking</legend>
      <label>Lat <input name="lat" type="number" step="any"></label>
      <label>Lon <input name="lon" type="number" step="any"></label>
      <label>Magnetic deviation (drot) <input name="drot" type="number" step="any"></label>
      <label>Time start (Y M D h m s) <input name="time_start_raw" placeholder="2015 4 11 17 36 23.0"></label>
      <label>Time end (Y M D h m s) <input name="time_end_raw" placeholder="2015 4 11 21 9 42.0"></label>
      <label>Bottom-track mode <input name="btrk_mode" type="number"></label>
      <label>Bottom-track used <input name="btrk_used" type="number"></label>
    </fieldset>

    <button type="submit">Save cast</button>
  </form>
</section>

<section id="generate-section">
  <button id="generate">Generate set_cast_params.m</button>
  <pre id="generate-result"></pre>
</section>
{% endblock %}
{% block scripts %}<script src="/static/app.js"></script>{% endblock %}
```

- [ ] **Step 2: Create a minimal stylesheet**

Create `webapp/static/style.css`:
```css
body { font-family: sans-serif; margin: 1.5rem; }
fieldset { margin-bottom: 1rem; }
label { display: block; margin: 0.25rem 0; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ccc; padding: 0.25rem 0.5rem; text-align: left; }
#ctd-preview table, #nav-preview table { font-size: 0.85rem; }
.error { color: #b00020; }
.warning { color: #8a6d00; }
```

- [ ] **Step 3: Implement `webapp/static/app.js`**

```javascript
const state = { editingCastId: null };

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw { status: response.status, body };
  }
  return response.status === 204 ? null : response.json();
}

async function refreshCastTable() {
  const session = await api("/api/session");
  document.getElementById("cruise-id").value = session.cruise_id || "";
  const tbody = document.querySelector("#cast-table tbody");
  tbody.innerHTML = "";
  for (const cast of session.casts) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${cast.cast_name || ""}</td>
      <td>${cast.ladcp_station ?? ""}</td>
      <td>${cast.lat ?? ""}</td>
      <td>${cast.lon ?? ""}</td>
      <td>
        <button data-edit="${cast.id}">Edit</button>
        <button data-clone="${cast.id}">Clone</button>
        <button data-remove="${cast.id}">Remove</button>
      </td>`;
    tbody.appendChild(row);
  }
}

async function openEditor(castId) {
  const session = await api("/api/session");
  const cast = session.casts.find((c) => c.id === castId) || {};
  state.editingCastId = castId || null;
  const form = document.getElementById("cast-form");
  form.reset();
  for (const [key, value] of Object.entries(cast)) {
    const field = form.elements.namedItem(key);
    if (field) field.value = value ?? "";
  }
  if (cast.time_start) form.elements.namedItem("time_start_raw").value = cast.time_start.join(" ");
  if (cast.time_end) form.elements.namedItem("time_end_raw").value = cast.time_end.join(" ");
  document.getElementById("cast-editor").hidden = false;
  await loadLadcpSuggestions();
}

async function loadLadcpSuggestions() {
  let data;
  try {
    data = await api("/api/ladcp/scan");
  } catch (e) {
    return;
  }
  const select = document.getElementById("ladcp-suggestions");
  select.innerHTML = "";
  for (const cast of data.casts) {
    const option = document.createElement("option");
    option.value = JSON.stringify(cast);
    option.textContent = `station ${cast.station}: ${cast.down || "?"} / ${cast.up || "?"}`;
    select.appendChild(option);
  }
}

document.getElementById("apply-ladcp-suggestion").addEventListener("click", () => {
  const select = document.getElementById("ladcp-suggestions");
  if (!select.value) return;
  const chosen = JSON.parse(select.value);
  const form = document.getElementById("cast-form");
  form.elements.namedItem("ladcp_station").value = parseInt(chosen.station, 10);
  form.elements.namedItem("ladcpdo").value = chosen.down || "";
  form.elements.namedItem("ladcpup").value = chosen.up || "";
  form.elements.namedItem("cast_name").value = chosen.station;
});

async function renderPreview(mount, pathInputId, targetDivId, roleFields) {
  const path = document.getElementById(pathInputId).value;
  if (!path) return;
  const preview = await api(`/api/preview/${mount}?path=${encodeURIComponent(path)}`);
  const div = document.getElementById(targetDivId);
  const form = document.getElementById("cast-form");
  form.elements.namedItem(`${mount === "ctd" ? "ctd" : "nav"}_header_lines`).value = preview.header_lines;
  form.elements.namedItem(`${mount === "ctd" ? "ctd" : "nav"}_fields_per_line`).value = preview.fields_per_line;

  let html = "<table><tr>";
  for (let col = 0; col < preview.fields_per_line; col++) {
    html += `<th><select data-col="${col}"><option value="">-</option>`;
    for (const role of roleFields) {
      html += `<option value="${role}">${role}</option>`;
    }
    html += "</select></th>";
  }
  html += "</tr>";
  for (const row of preview.preview_rows) {
    html += "<tr>" + row.map((v) => `<td>${v}</td>`).join("") + "</tr>";
  }
  html += "</table>";
  div.innerHTML = html;

  div.querySelectorAll("select[data-col]").forEach((select) => {
    select.addEventListener("change", () => {
      const col = parseInt(select.dataset.col, 10) + 1;
      const role = select.value;
      if (!role) return;
      const fieldName = `${mount === "ctd" ? "ctd" : "nav"}_${role}_field`;
      const field = form.elements.namedItem(fieldName);
      if (field) field.value = col;
    });
  });
}

document.getElementById("preview-ctd").addEventListener("click", () => {
  renderPreview("ctd", "ctd-path", "ctd-preview", ["time", "pressure", "temperature", "salinity"]);
});
document.getElementById("preview-nav").addEventListener("click", () => {
  renderPreview("nav", "nav-path", "nav-preview", ["time", "lat", "lon"]);
});

document.getElementById("add-cast").addEventListener("click", async () => {
  const created = await api("/api/session/casts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  await refreshCastTable();
  await openEditor(created.id);
});

document.querySelector("#cast-table tbody").parentElement.addEventListener("click", async (event) => {
  const editId = event.target.dataset.edit;
  const cloneId = event.target.dataset.clone;
  const removeId = event.target.dataset.remove;
  if (editId) await openEditor(editId);
  if (cloneId) {
    await api(`/api/session/casts/${cloneId}/clone`, { method: "POST" });
    await refreshCastTable();
  }
  if (removeId) {
    await api(`/api/session/casts/${removeId}`, { method: "DELETE" });
    await refreshCastTable();
  }
});

document.getElementById("cast-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target;
  const payload = {};
  for (const element of form.elements) {
    if (!element.name || element.name.endsWith("_raw")) continue;
    if (element.value === "") continue;
    payload[element.name] = element.type === "number" ? Number(element.value) : element.value;
  }
  const startRaw = form.elements.namedItem("time_start_raw").value;
  const endRaw = form.elements.namedItem("time_end_raw").value;
  if (startRaw) payload.time_start = startRaw.trim().split(/\s+/).map(Number);
  if (endRaw) payload.time_end = endRaw.trim().split(/\s+/).map(Number);

  await api(`/api/session/casts/${state.editingCastId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  document.getElementById("cast-editor").hidden = true;
  await refreshCastTable();
});

document.getElementById("generate").addEventListener("click", async () => {
  const result = document.getElementById("generate-result");
  try {
    const body = await api("/api/generate", { method: "POST" });
    result.textContent = `Written to ${body.written_to}`;
    result.className = "";
  } catch (e) {
    result.textContent = JSON.stringify(e.body, null, 2);
    result.className = "error";
  }
});

refreshCastTable();
```

- [ ] **Step 4: Wire the templates/static files and index route into `webapp/main.py`**

Modify `webapp/main.py` — add imports and route:
```python
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from webapp import api, config, delimited_parser, file_browser, ladcp_scan, paths

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
```
```python
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")
```

- [ ] **Step 5: Manually verify the page loads**

Run: `python -m uvicorn webapp.main:app --reload --port 8080` (from repo root, in the background)
Open `http://localhost:8080/` in a browser.
Expected: page loads with "Cruise/Cast Intake" heading, an empty cast table, and an "Add cast" button with no console errors.

Stop the server (Ctrl+C or kill the background process) once confirmed.

- [ ] **Step 6: Run the full backend test suite to confirm no regressions**

Run: `python -m pytest webapp/tests -v`
Expected: all tests pass (route addition doesn't change any existing endpoint behavior)

- [ ] **Step 7: Commit**

```bash
git add webapp/templates webapp/static webapp/main.py
git commit -m "feat: add cast intake web UI (list, editor, LADCP/CTD/nav pickers, generate)"
```

---

## Task 13: Documentation updates

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: nothing (docs only)
- Produces: nothing consumed by later tasks

- [ ] **Step 1: Update `README.md`'s Usage section for the new default entrypoint and mounts**

Modify `README.md` — replace the "Usage" section (currently steps 1–3 plus the non-interactive example) with:

```markdown
## Usage

### Web intake form (default)

`docker run ldeo-ix-octave` starts a web server on port 8080 for building
`set_cast_params.m` through a form instead of hand-editing it. Mount your
working directory at `/data`, plus whichever source-data directories you
have, then open the form in a browser:

```bash
docker run --rm -p 8080:8080 \
  -v "$(pwd)/my_cruise:/data" \
  -v "$(pwd)/my_cruise/raw:/ladcp_data" \
  -v "$(pwd)/my_cruise/ctd:/ctd_data" \
  -v "$(pwd)/my_cruise/sadcp:/sadcp_data" \
  -v "$(pwd)/my_cruise/nav:/navigation_data" \
  ldeo-ix-octave
```

Open `http://localhost:8080/` and add each cast — the form suggests raw
LADCP file pairs, lets you preview and column-map CTD/nav files, and can
clone a previous cast (in this session, or from a prior processed cast's
output `.nc`) as a starting point. Generating writes `/data/set_cast_params.m`
(backing up any existing file first).

### Direct Octave CLI

The original CLI workflow (LDEO_IX expects one `set_cast_params.m` per cast,
plus the cast's raw data, in your current working directory —
`process_cast.m` loads it automatically) is still available:

```bash
docker run --rm -it -v "$(pwd)/my_cast:/data" ldeo-ix-octave octave-cli
```

This drops you into `octave-cli` with `ldeo_ix/` and `stubs/` already on
the path. Process a cast:

```octave
process_cast(3)              % process station/cast 3
process_cast(3, 1, 2)        % run all 17 steps without stopping
```

See the docstring in `ldeo_ix/process_cast.m` for the full step list,
checkpoint/resume behavior, and `begin_step`/`stop` arguments. You can also
run a script non-interactively:

```bash
docker run --rm -v "$(pwd)/my_cast:/data" ldeo-ix-octave octave-cli --eval "process_cast(3,1,2)"
```
```

- [ ] **Step 2: Update the "What's in here" list in `README.md`**

Modify `README.md` — add a bullet after the `examples/` bullet:
```markdown
- `webapp/` — the web intake form (FastAPI + vanilla JS) that generates
  `set_cast_params.m`; see `docs/superpowers/specs/2026-07-15-cruise-cast-intake-form-design.md`
  for its design.
```

- [ ] **Step 3: Update `CLAUDE.md`'s repo layout table**

Modify `CLAUDE.md` — add a row to the "Repo layout" table after the `examples/` row:
```markdown
| `webapp/` | Web intake form (FastAPI + Jinja2 + vanilla JS) that generates `set_cast_params.m`. No Node/build toolchain. Tests live in `webapp/tests/`, run via `python -m pytest webapp/tests`. |
```

Also add a bullet to "Working conventions":
```markdown
- `webapp/` changes should keep the pure-logic modules (`paths.py`,
  `delimited_parser.py`, `ladcp_scan.py`, `netcdf_reader.py`,
  `template_gen.py`, `validation.py`) unit-tested; UI/route wiring is
  verified manually (`python -m uvicorn webapp.main:app` + browser, or a
  full `docker build`/`docker run`) per the pattern in
  `docs/superpowers/specs/2026-07-15-cruise-cast-intake-form-design.md`.
```

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: document the web intake form's usage, mounts, and layout"
```

---

## Task 14: Full end-to-end verification against the P16N example

**Files:**
- None created/modified — verification only.

**Interfaces:**
- Consumes: the fully built image (Tasks 1–13)

- [ ] **Step 1: Build the image**

Run: `docker build -t ldeo-ix-octave:local .`

- [ ] **Step 2: Set up a mock cruise directory matching the example's fields**

Run:
```bash
mkdir -p /tmp/p16n_test/data /tmp/p16n_test/raw /tmp/p16n_test/ctd
: > /tmp/p16n_test/raw/003DL000.000
: > /tmp/p16n_test/raw/003UL000.000
python3 -c "
import random
lines = []
t0 = 0.0
for i in range(20):
    lines.append(f'{t0+i} {5+i*0.01} {12+i*0.01} {34.9+i*0.001} 0 0 0 0 0 -15.498335 -150.19699')
open('/tmp/p16n_test/ctd/003.2Hz', 'w').write(chr(10).join(lines) + chr(10))
"
```

- [ ] **Step 3: Run the container against the mock directory**

Run:
```bash
docker run --rm -d -p 8080:8080 --name p16n-test \
  -v /tmp/p16n_test/data:/data \
  -v /tmp/p16n_test/raw:/ladcp_data \
  -v /tmp/p16n_test/ctd:/ctd_data \
  -v /tmp/p16n_test/ctd:/navigation_data \
  ldeo-ix-octave:local
```

- [ ] **Step 4: Drive the intake flow through the API (standing in for manual browser interaction, for repeatability)**

Run:
```bash
curl -s -X POST http://localhost:8080/api/session/casts -H "Content-Type: application/json" -d '{
  "cast_name": "003", "ladcp_station": 3, "ladcp_cast": 1,
  "ladcpdo": "003DL000.000", "ladcpup": "003UL000.000",
  "ctd": "003.2Hz", "nav": "003.2Hz",
  "ctd_header_lines": 0, "ctd_fields_per_line": 11,
  "ctd_time_field": 1, "ctd_pressure_field": 2, "ctd_temperature_field": 3, "ctd_salinity_field": 4,
  "nav_header_lines": 0, "nav_fields_per_line": 11,
  "nav_time_field": 1, "nav_lat_field": 10, "nav_lon_field": 11,
  "drot": 12.318441, "lat": -15.498335, "lon": -150.19699,
  "time_start": [2015, 4, 11, 17, 36, 23.312975],
  "time_end": [2015, 4, 11, 21, 9, 42.220459],
  "btrk_mode": 3, "btrk_used": 1
}'
curl -s -X POST http://localhost:8080/api/generate
```
Expected: second response has `"written_to"` pointing at `/data/set_cast_params.m` and no `errors` key.

- [ ] **Step 5: Compare the generated file's field values against the example**

Run: `cat /tmp/p16n_test/data/set_cast_params.m`

Manually compare against `examples/set_cast_params_P16N_example.m` — every field present in the example (`f.ladcpdo`, `p.lat`, `p.time_start`, etc.) should appear with the same value in the generated file. Exact formatting/ordering may differ; field values must match.

- [ ] **Step 6: Verify Octave can actually load the generated file without error**

Run:
```bash
docker exec p16n-test octave-cli --no-gui --eval "
f=struct();p=struct();ps=struct();att=struct();
cd /data; stn=3;
run('/data/set_cast_params.m');
disp(p.lat); disp(p.lon); disp(f.ladcpdo);
"
```
Expected: prints `-15.498335`, `-150.19699`, `003DL000.000` with no errors.

- [ ] **Step 7: Clean up**

Run: `docker stop p16n-test`
Run: `rm -rf /tmp/p16n_test`

- [ ] **Step 8: No commit needed — this task is verification only.** If any step failed, fix the relevant module from Tasks 1–13, re-run its unit tests, then re-run this task from Step 1.

---

## Self-Review Notes

- **Spec coverage:** file browsing/mounts (Task 3), CTD/nav sniffing + column mapping (Tasks 4, 12), LADCP smart pairing (Tasks 5, 12), netCDF cloning (Tasks 6, 10), session sidecar persistence (Task 7), template generation matching the example's style (Task 8), required-field/file-existence validation (Task 9), generate-with-backup (Task 11), Docker entrypoint switch and named mounts (Tasks 1, 13), manual E2E verification against the P16N example (Task 14) — every section of the design doc has a corresponding task.
- **Placeholder scan:** no TBD/TODO markers; the one open item (netCDF format assumption) has concrete verification steps in Task 6, not a placeholder.
- **Type consistency:** `CastEntry`/`CruiseSession` (Task 7) are the single source of truth for field names; `template_gen.py` (Task 8), `validation.py` (Task 9), and `api.py` (Tasks 10–11) all reference the same attribute names (`ladcpdo`, `ctd_time_field`, `checkpoints_file`, etc.) — checked for drift across tasks during writing.
