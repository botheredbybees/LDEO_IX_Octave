# magdec Replacement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install a real, working `magdec` command in the `ldeo-ix-octave` Docker image so `ldeo_ix/loadnav.m` computes magnetic declination from a real, current IGRF model instead of silently falling back to a hardcoded year-2000 model, and prove it works against a real cast.

**Architecture:** A small, original Python CLI (`magdec/magdec.py`) matching `loadnav.m`'s exact existence-probe/compute contract, built on `ppigrf` (a maintained, pure-Python IGRF-14 implementation), installed onto the image's `$PATH` at `/usr/local/bin/magdec` via one new Dockerfile block.

**Tech Stack:** Python 3 (`.venv312`, matching this repo's existing testing convention), `ppigrf` 2.1.0, Docker, GNU Octave (live verification only).

## Global Constraints

- Work directly on branch `master` in `/home/peter_sha/sourcecode/Nuyina/LDEO_IX_Octave` — no git worktrees.
- No AI-authorship commit trailers on any commit.
- `loadnav.m:264-272`'s exact contract (verified directly against the real file this session, not assumed) governs `magdec`'s CLI behavior:
  - Called with **zero arguments**: must exit with status **exactly 1** (not 0, not any other value) — this is the existence probe `[s,o]=system('magdec'); if s==1 ... end` checks. Confirmed independently by Andreas Thurnherr's own LDEO_IX manual.
  - Called with **five arguments** (`lon lat year month day`): must exit **0** and print at least 4 whitespace-separated numbers to stdout, the first being declination in degrees (`loadnav.m:332-364`'s `geomag()` subfunction reads only `vals(1)`).
  - Any other argument count: no real call pattern exists for this; treat it the same as zero arguments (usage + exit 1) as a safe default.
- **Sign convention**: declination is `atan2(east_component, north_component)` in degrees, matching the existing `ldeo_ix/magdev.m` fallback's `atan2(Y,X)` (X=north, Y=east) convention. Getting this backwards silently flips every declination this pipeline computes.
- `ppigrf.igrf(lon, lat, h, date)` requires a `datetime.datetime` for its `date` argument, **not** `datetime.date` — confirmed by direct testing this session: `datetime.date` raises `TypeError: Cannot compare Timestamp with datetime.date` from inside `ppigrf`'s internal pandas-based coefficient lookup. Also confirmed: `ppigrf.igrf()` returns 1-element numpy arrays for a scalar input, not plain floats — extract with `.item()`, not a bare `float()` call (which works today but raises a `DeprecationWarning` under `-W error::DeprecationWarning`, confirmed this session, and will error in a future numpy).
- Real reference values, already confirmed this session and load-bearing for the plan's tests: for voyage 202324050 cast 005's real position (`lon=148.490637, lat=-42.559128`) on `2024-06-17`, the existing `magdev.m` (year-2000 IGRF00) fallback produced `p.drot = 15.057159` (observed identically across all three real casts processed this session, due to a separate, already-fixed navigation-table-windowing bug that made them share one median position). A correct `ppigrf`/IGRF-14 computation for this exact position/date, confirmed by direct testing this session, gives declination `≈15.883°` — same sign, a small (`<1°`) delta, consistent with real secular variation over ~24 years, not a sign flip or wild divergence.
- Docker image tags currently on this machine: `ldeo-ix-octave:local` and `ldeo-ix-octave` (bare, i.e. `:latest`) both point at the same already-built image (`d52b0408447d`) as of this session, via an earlier `docker tag ldeo-ix-octave:local ldeo-ix-octave:latest`. Both tags are used by `scripts/process_cast.sh` (default tag `ldeo-ix-octave`) and its Nuyina-specific caller `nuyina_data/scripts/process_nuyina_cast.sh` (uncommitted, calls with no explicit tag) — after rebuilding, both tags must be re-pointed at the new image or those scripts will run against the stale one.
- Test baseline: `.venv312/bin/python -m pytest webapp/tests scripts/test_gngga_to_navtable.py` currently passes 114/114. No task in this plan touches `webapp/` or `scripts/gngga_to_navtable.py` — this must stay 114/114 throughout.
- Tasks that involve live Docker/Octave execution depend on real, live infrastructure. If that infrastructure is unavailable when a task runs, the task must report BLOCKED with the real error — never fabricate or reconstruct plausible-looking output. Every "real output" quoted in a task report must be copy-pasted verbatim from an actual command run in that task.

---

### Task 1: `magdec/magdec.py` — the tool itself, with unit tests

**Files:**
- Create: `magdec/magdec.py`
- Create: `magdec/requirements.txt`
- Create: `magdec/test_magdec.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `compute(lon: float, lat: float, year: int, month: int, day: int) -> tuple[float, float, float, float]` (declination, inclination, horizontal intensity, total intensity — all in the units `ppigrf` itself uses: degrees, degrees, nT, nT) and `main(argv: list[str]) -> int`, the CLI entry point. Task 2 copies `magdec/magdec.py` verbatim into the Docker image as `/usr/local/bin/magdec` — its file content must not need any modification to run standalone (no relative imports, no repo-relative paths).

- [ ] **Step 1: Write the failing tests**

```python
# magdec/test_magdec.py
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from magdec import compute, main

SCRIPT = Path(__file__).resolve().parent / "magdec.py"

# Real position/date from voyage 202324050 cast 005, processed for real
# this session. The already-known-good magdev.m (year-2000 IGRF00)
# fallback declination for this exact position was 15.057159 degrees,
# independently confirmed multiple times this session. A correct,
# modern (IGRF-14, 2024) computation for the same real position lands
# in the same ballpark (same sign, small delta -- secular variation
# over ~25 years is real but bounded), not a sign flip or wild
# divergence -- confirmed directly this session: 15.883 degrees.
CAST_005_LON = 148.490637
CAST_005_LAT = -42.559128


def test_compute_matches_known_sign_and_magnitude_for_real_cast_005_position():
    declination, inclination, horizontal, total = compute(
        CAST_005_LON, CAST_005_LAT, 2024, 6, 17
    )

    assert 10.0 < declination < 20.0
    assert -90.0 <= inclination <= 90.0
    assert 1000.0 < horizontal < 100000.0
    assert 1000.0 < total < 100000.0


def test_main_with_no_args_exits_1_with_usage_on_stderr(capsys):
    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "usage" in captured.err.lower()


def test_main_with_wrong_arg_count_exits_1():
    exit_code = main(["148.49", "-42.56", "2024"])

    assert exit_code == 1


def test_main_with_five_args_exits_0_and_prints_four_numbers(capsys):
    exit_code = main(["148.490637", "-42.559128", "2024", "6", "17"])

    captured = capsys.readouterr()
    assert exit_code == 0
    values = [float(x) for x in captured.out.split()]
    assert len(values) == 4


def test_cli_no_args_real_subprocess_exits_1():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True
    )

    assert result.returncode == 1
    assert "usage" in result.stderr.lower()


def test_cli_five_args_real_subprocess_exits_0():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "148.490637", "-42.559128", "2024", "6", "17"],
        capture_output=True, text=True,
    )

    assert result.returncode == 0
    values = [float(x) for x in result.stdout.split()]
    assert len(values) == 4
    assert 10.0 < values[0] < 20.0
```

- [ ] **Step 2: Install `ppigrf` into `.venv312` and run the tests to verify they fail**

```bash
.venv312/bin/pip install ppigrf
.venv312/bin/python -m pytest magdec/test_magdec.py -v
```

Expected: `ModuleNotFoundError: No module named 'magdec'` or a collection error — `magdec/magdec.py` doesn't exist yet.

- [ ] **Step 3: Write `magdec/requirements.txt`**

```
ppigrf
```

- [ ] **Step 4: Write `magdec/magdec.py`**

```python
#!/usr/bin/env python3
"""magdec -- CLI replacement for Eric Firing's original magdec tool that
ldeo_ix/loadnav.m's geomag() subfunction shells out to. Uses ppigrf
(IGRF-14, IAGA-VMOD) instead of the original tool's own bundled model,
since every official distribution channel for the original binary is
unreachable as of 2026-09-06 (see CHANGES.md).

Two calling conventions, both dictated by ldeo_ix/loadnav.m's own logic
(NOT a general-purpose CLI design choice -- see
docs/superpowers/specs/2026-09-06-magdec-replacement-design.md):
- zero arguments: existence probe. loadnav.m's `[s,o]=system('magdec')`
  checks specifically for exit status 1 to decide whether to use this
  tool at all -- print usage, exit 1.
- five arguments (lon lat year month day): print
  "declination inclination horizontal_intensity total_intensity",
  space-separated, one line, exit 0. Only the first value (declination)
  is actually read by loadnav.m; the rest exist for output-shape parity
  with the original tool.
"""
import math
import sys
from datetime import datetime


def compute(lon: float, lat: float, year: int, month: int, day: int) -> tuple:
    import ppigrf

    # ppigrf compares its date argument against a pandas DatetimeIndex
    # internally -- a plain datetime.date raises TypeError there
    # ("Cannot compare Timestamp with datetime.date"), confirmed by
    # running this for real; datetime.datetime works.
    Be, Bn, Bu = ppigrf.igrf(lon, lat, 0.0, datetime(year, month, day))
    # ppigrf returns 1-element numpy arrays for a scalar input point,
    # not plain floats -- float() on one works today but is deprecated
    # (confirmed via -W error::DeprecationWarning), so extract with
    # .item() instead.
    Be, Bn, Bu = float(Be.item()), float(Bn.item()), float(Bu.item())

    horizontal = math.hypot(Be, Bn)
    declination = math.degrees(math.atan2(Be, Bn))
    inclination = math.degrees(math.atan2(-Bu, horizontal))
    total = math.sqrt(Be ** 2 + Bn ** 2 + Bu ** 2)
    return declination, inclination, horizontal, total


def main(argv) -> int:
    if len(argv) != 5:
        print("usage: magdec <lon> <lat> <year> <month> <day>", file=sys.stderr)
        return 1
    lon, lat = float(argv[0]), float(argv[1])
    year, month, day = int(argv[2]), int(argv[3]), int(argv[4])
    d, i, h, f = compute(lon, lat, year, month, day)
    print(f"{d:.4f} {i:.4f} {h:.1f} {f:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 5: Make it executable and run the tests to verify they pass**

```bash
chmod +x magdec/magdec.py
.venv312/bin/python -m pytest magdec/test_magdec.py -v
```

Expected: 7 passed.

- [ ] **Step 6: Confirm the existing test suites are unaffected**

```bash
.venv312/bin/python -m pytest webapp/tests scripts/test_gngga_to_navtable.py
```

Expected: 114 passed (this task touches neither directory).

- [ ] **Step 7: Commit**

```bash
git add magdec/magdec.py magdec/requirements.txt magdec/test_magdec.py
git commit -m "$(cat <<'EOF'
feat: add magdec CLI replacement using ppigrf (IGRF-14)

The original Eric Firing magdec/geomag tool loadnav.m expects has no
reachable distribution channel (SOEST hgweb 404, LDEO FTP connection
refused, Thurnherr's own current hgweb link 500s). Replaces it with a
small, original tool built on ppigrf, matching loadnav.m's exact
exit-code/output contract exactly.
EOF
)"
```

---

### Task 2: Wire `magdec` into the Docker image

**Files:**
- Modify: `Dockerfile`

**Interfaces:**
- Consumes: `magdec/magdec.py`, `magdec/requirements.txt` from Task 1.
- Produces: a rebuilt `ldeo-ix-octave` image with a real `magdec` on `$PATH`. Task 3 and Task 4 both depend on this image existing and being current.

This task requires Docker. If Docker is unavailable when this task runs, report BLOCKED with the real error rather than proceeding.

- [ ] **Step 1: Add the new Dockerfile block**

Insert this block immediately after the existing webapp install lines (`COPY webapp/ /opt/webapp/` / `ENV PYTHONPATH=/opt`) and before `EXPOSE 8080`:

```dockerfile
# Real magdec replacement (ldeo_ix/loadnav.m shells out to a command
# named magdec on $PATH -- see docs/superpowers/specs/
# 2026-09-06-magdec-replacement-design.md for why this is a from-scratch
# tool rather than the original, now-unreachable, distribution).
COPY magdec/requirements.txt /opt/magdec/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /opt/magdec/requirements.txt
COPY magdec/magdec.py /usr/local/bin/magdec
RUN chmod +x /usr/local/bin/magdec
```

The full relevant section of `Dockerfile` should now read:

```dockerfile
COPY webapp/requirements.txt /opt/webapp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /opt/webapp/requirements.txt
COPY webapp/ /opt/webapp/
ENV PYTHONPATH=/opt

# Real magdec replacement (ldeo_ix/loadnav.m shells out to a command
# named magdec on $PATH -- see docs/superpowers/specs/
# 2026-09-06-magdec-replacement-design.md for why this is a from-scratch
# tool rather than the original, now-unreachable, distribution).
COPY magdec/requirements.txt /opt/magdec/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /opt/magdec/requirements.txt
COPY magdec/magdec.py /usr/local/bin/magdec
RUN chmod +x /usr/local/bin/magdec

EXPOSE 8080
```

- [ ] **Step 2: Rebuild the image**

```bash
docker build -t ldeo-ix-octave .
```

Expected: builds successfully (watch for the new `pip3 install -r /opt/magdec/requirements.txt` layer actually installing `ppigrf`).

- [ ] **Step 3: Re-tag so existing tooling picks up the new image**

```bash
docker tag ldeo-ix-octave:latest ldeo-ix-octave:local
docker images ldeo-ix-octave
```

Expected: both `ldeo-ix-octave:latest` and `ldeo-ix-octave:local` show the same, new image ID — different from the pre-rebuild `d52b0408447d` recorded in this plan's Global Constraints.

- [ ] **Step 4: Confirm the existing test suites are unaffected**

```bash
.venv312/bin/python -m pytest webapp/tests scripts/test_gngga_to_navtable.py magdec/test_magdec.py
```

Expected: 121 passed (114 pre-existing + 7 from Task 1) — a Dockerfile-only change touches none of these test files.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile
git commit -m "$(cat <<'EOF'
feat: install magdec on the Docker image's PATH

One new pip3 install + COPY + chmod block, following the same pattern
already used for webapp's own Python dependencies.
EOF
)"
```

---

### Task 3: Live verification — `magdec`'s own CLI behavior

**Files:** none (verification only, no commit)

**Interfaces:**
- Consumes: the rebuilt image from Task 2.
- Produces: nothing consumed by later tasks — a verification gate proving Task 1/2's work actually behaves correctly inside the real image before Task 4 depends on it.

This task requires Docker and the image rebuilt in Task 2.

- [ ] **Step 1: Confirm the zero-argument exit-code contract**

```bash
docker run --rm ldeo-ix-octave magdec
echo "exit: $?"
```

Expected: prints the usage message to stderr, `exit: 1`. This is the single most important check in this task — if this isn't exactly `1`, `loadnav.m` will never take the real-computation branch no matter what the five-argument case does.

- [ ] **Step 2: Confirm the five-argument contract with cast 005's real position**

```bash
docker run --rm ldeo-ix-octave magdec 148.490637 -42.559128 2024 6 17
echo "exit: $?"
```

Expected: `exit: 0`, and a line with 4 numbers, the first between `10` and `20` (matching this plan's Global Constraints' already-confirmed real value, `≈15.883`).

- [ ] **Step 3: Record the real captured output**

The task report must quote the actual terminal output of Steps 1 and 2 verbatim.

No commit for this task.

---

### Task 4: Live verification — real cast 005 re-run

**Files:** none (verification only, no commit)

**Interfaces:**
- Consumes: the rebuilt image from Task 2, the real `nuyina_data/202324050_005/` staging directory (already populated from earlier sessions), `scripts/process_cast.sh` (unmodified by this plan).
- Produces: nothing consumed by later tasks.

This task requires Docker and reuses the existing staging directory and its `cast-config.json` — do not recreate it. If `nuyina_data/202324050_005/cast-config.json` is missing, recreate it with these exact real values (from the prior plan's own Task 4):

```json
{
  "station": 5,
  "cast_name": "202324050_005",
  "ladcpdo": "2324050_005_down_ladcp.000",
  "ladcpup": "2324050_005_up_ladcp.000",
  "ctd_hex": "202324050_005.hex",
  "ctd_xmlcon": "202324050_005.XMLCON",
  "ctd_header_lines": 283,
  "ctd_fields_per_line": 19,
  "ctd_time_field": 11,
  "ctd_pressure_field": 2,
  "ctd_temperature_field": 3,
  "ctd_salinity_field": 5,
  "ctd_badvals": -9e99,
  "ctd_time_base": 0,
  "nav": "202324050_005.navtable",
  "nav_header_lines": 0,
  "nav_fields_per_line": 3,
  "nav_time_field": 1,
  "nav_lat_field": 2,
  "nav_lon_field": 3,
  "sadcp_contour_dir": "contour",
  "lat": -42.559128,
  "lon": 148.490637,
  "time_start": [2024, 6, 17, 3, 43, 15],
  "time_end": [2024, 6, 17, 4, 24, 28.917]
}
```

- [ ] **Step 1: Run it**

```bash
scripts/process_cast.sh nuyina_data/202324050_005 nuyina_data/202324050_005/cast-config.json ldeo-ix-octave:local
```

Expected: exits 0, runs to completion.

- [ ] **Step 2: Confirm the real geomag() branch was taken**

```bash
docker run --rm -v "$(pwd)/nuyina_data/202324050_005/data:/data" ldeo-ix-octave:local \
  octave-cli --eval "process_cast(5,1,0)" 2>&1 | grep -i "magdec\|magnetic declination"
```

(This re-runs `process_cast` a second time purely to capture its console output for inspection — the log printed during Step 1's real run is equally valid evidence if it was captured; use whichever real output is actually available, and quote it verbatim either way.)

Expected: a line reading `corrected for magnetic declination of <N> deg` — and **critically, no** `"magdec" not found; using old magdev code with IGRF00` warning line. If the warning still appears, this is a real, load-bearing failure (Task 1/2 didn't actually get picked up) — report BLOCKED with the full real log, don't proceed to Step 3.

- [ ] **Step 3: Confirm the real declination differs from the old fallback value**

```bash
docker run --rm -v "$(pwd)/nuyina_data/202324050_005/data:/data" ldeo-ix-octave:local \
  octave-cli --eval "load /data/V7/202324050_005.mat; printf('drot: %.6f\n', p.drot)"
```

Expected: a real value close to `15.883` (this plan's Global Constraints' already-confirmed `ppigrf`-computed value for this exact position/date) and **different from** `15.057159` (the old fallback value, confirmed identically across all three casts processed earlier this session). A value that still exactly matches `15.057159` means the fix did not actually take effect — report BLOCKED, don't paper over it.

- [ ] **Step 4: Record the real captured output**

The task report must quote the actual terminal output of Steps 1-3 verbatim, including the real `p.drot` value obtained.

No commit for this task.

---

### Task 5: Documentation — `CHANGES.md`, `README.md`, `NOTICE.md`

**Files:**
- Modify: `CHANGES.md`
- Modify: `README.md`
- Modify: `NOTICE.md`

**Interfaces:**
- Consumes: the real, verified declination value from Task 4 (to cite as evidence in `CHANGES.md`, if Task 4 completed successfully — if Task 4 reported BLOCKED, do not write documentation claiming a fix that isn't verified working; escalate instead of proceeding to this task).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Read the current `CHANGES.md` entry that flagged this gap**

Read `CHANGES.md` in full first — an earlier session already added an entry noting "this Docker image ships no `magdec` binary." Find it before writing the new entry, so the new entry can reference it accurately rather than guessing its wording.

- [ ] **Step 2: Add a new `CHANGES.md` entry**

Append a new entry (following whatever format the existing entries use — read a couple of them first) stating: a real `magdec` command is now installed at `/usr/local/bin/magdec` (`magdec/magdec.py`, built on `ppigrf`/IGRF-14), closing the gap the earlier entry flagged. Not a patch to any `ldeo_ix/*.m` file — this restores the integration point `loadnav.m` already expected, without modifying any upstream file. Cite the real verification result from Task 4 (the actual `p.drot` value obtained for cast 005, and that it differed from the old `15.057159` fallback).

- [ ] **Step 3: Add a README.md subsection**

Read `README.md`'s "Why Octave instead of MATLAB" section (near the end of the file) for placement and tone, then add a new subsection immediately after it (or wherever reads most naturally given the file's actual current structure) explaining: the image includes a real `magdec` command backed by `ppigrf` (IGRF-14), because the original tool's own distribution channels are currently unreachable; this matters because without it, `loadnav.m` silently falls back to a hardcoded year-2000 magnetic model for every cast.

- [ ] **Step 4: Add a NOTICE.md line for `ppigrf`**

Read the existing `ctdam`/`seabirdscientific` entries in `NOTICE.md` first to match their exact format, then add one line for `ppigrf`: MIT-licensed, a pip dependency of `magdec/magdec.py`, maintained by IAGA-VMOD.

- [ ] **Step 5: Confirm the existing test suites are unaffected**

```bash
.venv312/bin/python -m pytest webapp/tests scripts/test_gngga_to_navtable.py magdec/test_magdec.py
```

Expected: 121 passed (docs-only change).

- [ ] **Step 6: Commit**

```bash
git add CHANGES.md README.md NOTICE.md
git commit -m "$(cat <<'EOF'
docs: document the magdec replacement

CHANGES.md closes the gap an earlier session's entry flagged; README.md
explains why the image includes its own magdec now; NOTICE.md adds the
ppigrf dependency, matching the existing ctdam/seabirdscientific entries.
EOF
)"
```
