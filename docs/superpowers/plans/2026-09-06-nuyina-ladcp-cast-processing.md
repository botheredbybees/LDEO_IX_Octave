# Real Nuyina LADCP Cast Processing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Process real RSV *Nuyina* LADCP cast 005 (voyage 202324050) end-to-end through `process_cast()`'s real 17 steps, using this cast's real CTD, real navigation, and `nuyina_uhdas_codas`'s already-produced real CODAS output as the SADCP reference.

**Architecture:** Stage real voyage data (CTD/nav pulled from the AAD shore S3 bucket; LADCP and CODAS output already local) into a directory tree matching the webapp's mount layout, convert a real navigation extract into the plain numeric format `loadnav.m` requires (a genuine gap found during design — neither the webapp's generic column-mapper nor `loadnav.m` itself accepts comma-delimited or non-numeric-time input), drive the webapp's existing API to generate `set_cast_params.m`, then run the real Octave pipeline and inspect its real output.

**Tech Stack:** bash (`rclone` for S3), Python 3 (nav conversion script — no new dependencies, stdlib only), the existing `ldeo-ix-octave:local` Docker image and webapp (unmodified), `curl` for driving the API.

## Global Constraints

- Cast 005 only. Casts 004/006 are not processed in this plan.
- Cast 005's real start time is `2024-06-17T03:43:15Z` (confirmed from `202324050_005.hdr`'s `System UTC` line) — use this exact value everywhere a cast-start reference is needed, not a placeholder or a value re-derived some other way.
- SADCP reference is OS150 (`nuyina_uhdas_codas/output/nuyina_202324050/os150nb/contour/`), not OS38.
- No change to the webapp (`webapp/*.py`) or to `ldeo_ix/*.m` in this plan — every API call and Octave invocation uses what's already shipped.
- The nav-conversion script is the one piece of genuinely new code this plan adds, and it stays outside `webapp/` and `ldeo_ix/` — a standalone data-conversion utility, not a change to either pipeline.
- All fetched voyage data and generated intermediate files live under a gitignored staging directory — nothing voyage-specific gets committed to this repo.
- `S3_HOST`/`S3_ACCESS_KEY`/`S3_SECRET_KEY`/`S3_BUCKET` are already set in the Nuyina workspace root `.env` (`/home/peter_sha/sourcecode/Nuyina/.env`) — read them from there, don't ask for them.

---

### Task 1: Stage real voyage data and build the nav-conversion script

**Files:**
- Create: `scripts/gngga_to_navtable.py`
- Create: `.gitignore` entry for `nuyina_data/` (the staging directory)

**Interfaces:**
- Consumes: nothing from earlier tasks (this is the first task).
- Produces: a staging directory `nuyina_data/202324050_005/` with subdirectories `ctd/`, `nav/`, `codas/`, `data/` populated as described below — Task 2 mounts these directly. Also produces `scripts/gngga_to_navtable.py`, invoked as `python3 scripts/gngga_to_navtable.py <input.csv> <output.txt>`, producing a 3-column whitespace-delimited file (`elapsed_seconds lat_decimal_degrees lon_decimal_degrees`, one row per fix, no header) — Task 2 mounts this output file and references its exact column layout in the cast session's nav field mapping (`nav_header_lines=0`, `nav_fields_per_line=3`, `nav_time_field=1`, `nav_lat_field=2`, `nav_lon_field=3`).

- [ ] **Step 1: Create the staging directory and fetch cast 005's real CTD data from S3**

```bash
mkdir -p nuyina_data/202324050_005/ctd nuyina_data/202324050_005/nav nuyina_data/202324050_005/codas nuyina_data/202324050_005/data
set -a
source /home/peter_sha/sourcecode/Nuyina/.env
set +a
export RCLONE_CONFIG_AADCKINGSTON_TYPE=s3
export RCLONE_CONFIG_AADCKINGSTON_PROVIDER=Other
export RCLONE_CONFIG_AADCKINGSTON_ENDPOINT="$S3_HOST"
export RCLONE_CONFIG_AADCKINGSTON_ACCESS_KEY_ID="$S3_ACCESS_KEY"
export RCLONE_CONFIG_AADCKINGSTON_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
for ext in hex XMLCON hdr bl; do
  rclone copyto "aadckingston:$S3_BUCKET/202324050/ctd/ctd_seabird/raw/seasave/202324050_005.$ext" \
    "nuyina_data/202324050_005/ctd/202324050_005.$ext"
done
```

Expected: `ls nuyina_data/202324050_005/ctd/` shows exactly 4 files (`.hex`, `.XMLCON`, `.hdr`, `.bl`).

- [ ] **Step 2: Confirm cast 005's real start time from the fetched `.hdr` file**

```bash
grep "System UTC" nuyina_data/202324050_005/ctd/202324050_005.hdr
```

Expected output: `* System UTC = Jun 17 2024 03:43:15` — confirming the Global Constraints value above. If this ever differs (e.g. a different cast is substituted later), every hardcoded `2024-06-17T03:43:15` / `2024, 6, 17, 3, 43, 15` value in this plan and in Step 4's script must be updated to match — don't silently keep the old value.

- [ ] **Step 3: Fetch the matching day's real GNGGA navigation extract from S3**

```bash
rclone copyto "aadckingston:$S3_BUCKET/202324050/dgps/proc/csv/GNGGA/GNGGA_2024-06-17.csv" \
  nuyina_data/202324050_005/nav/GNGGA_2024-06-17.csv
head -3 nuyina_data/202324050_005/nav/GNGGA_2024-06-17.csv
```

Expected: a CSV whose header row is `datetime,msg_id,gps_time_dgps_gga,latitude_dgps_gga,n_or_s_dgps_gga,longitude_dgps_gga,e_or_w_dgps_gga,fix_quality_dgps_gga,number_of_satellites_dgps_gga,horizontal_dilution_of_precision_dgps_gga,antenna_height_dgps_gga,geoid_height_above_reference_ellipsoid_dgps_gga,last_dgps_update_dgps_gga,differential_reference_station_id_dgps_gga`, with data rows like `2024-06-17T00:00:00.460655Z,$GNGGA,235959.00,4233.6601,S,14829.5473,E,1,14,0.7,35.3,M,-4.7,M,,`.

- [ ] **Step 4: Write the nav-conversion script**

This exists because neither the webapp's generic CTD/nav column-mapper nor `ldeo_ix/loadnav.m` accepts comma-delimited input, and both require the time column to be purely numeric — the raw GNGGA CSV's ISO-8601 `datetime` column and comma delimiters fail both (confirmed during design: the webapp's `/api/preview` endpoint returns `fields_per_line: 0` against this file, because `delimited_parser.py`'s sniffer splits on whitespace, not commas, and its data-line heuristic requires every token on a line to be numeric).

Create `scripts/gngga_to_navtable.py`:

```python
#!/usr/bin/env python3
"""Convert a Kongsberg GNGGA proc/csv extract (comma-delimited, ISO-8601
timestamp) into the plain whitespace-delimited, all-numeric table
ldeo_ix/loadnav.m's fscanf-based reader (and the LDEO_IX_Octave webapp's
generic column-mapper, which shares the same whitespace/all-numeric
assumption) require: elapsed_seconds lat_decimal_degrees lon_decimal_degrees,
one row per fix, no header.

elapsed_seconds is relative to CAST_START, which must be set to the exact
same value used for the cast's time_start field in set_cast_params.m --
loadctd.m and loadnav.m both convert their own elapsed-seconds columns to
an absolute Julian date via `p.time_start`, so a mismatch here would put
the CTD and nav time series on different absolute clocks.

This is a one-off, single-cast conversion script (not a generic tool) --
CAST_START is hardcoded to cast 005's real, confirmed start time rather
than parsed from a .hdr file, since generalizing that isn't needed for
processing this one cast. See
docs/superpowers/specs/2026-09-06-nuyina-ladcp-cast-processing-design.md
for why this script exists at all.
"""
import csv
import sys
from datetime import datetime, timezone

CAST_START = datetime(2024, 6, 17, 3, 43, 15, tzinfo=timezone.utc)


def nmea_to_decimal(value: str, hemisphere: str) -> float:
    """Convert NMEA ddmm.mmmm (or dddmm.mmmm for longitude) to decimal degrees."""
    raw = float(value)
    degrees = int(raw / 100)
    minutes = raw - degrees * 100
    decimal = degrees + minutes / 60
    if hemisphere in ("S", "W"):
        decimal = -decimal
    return decimal


def convert(csv_path: str, out_path: str) -> int:
    rows_written = 0
    with open(csv_path, newline="") as fh, open(out_path, "w") as out:
        reader = csv.DictReader(fh)
        for row in reader:
            timestamp = datetime.fromisoformat(row["datetime"].replace("Z", "+00:00"))
            elapsed_seconds = (timestamp - CAST_START).total_seconds()
            lat = nmea_to_decimal(row["latitude_dgps_gga"], row["n_or_s_dgps_gga"])
            lon = nmea_to_decimal(row["longitude_dgps_gga"], row["e_or_w_dgps_gga"])
            out.write(f"{elapsed_seconds:.3f} {lat:.6f} {lon:.6f}\n")
            rows_written += 1
    return rows_written


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <input GNGGA csv> <output nav table>", file=sys.stderr)
        sys.exit(1)
    count = convert(sys.argv[1], sys.argv[2])
    print(f"wrote {count} rows to {sys.argv[2]}")
```

- [ ] **Step 5: Run the conversion against cast 005's real fetched nav data**

```bash
python3 scripts/gngga_to_navtable.py \
  nuyina_data/202324050_005/nav/GNGGA_2024-06-17.csv \
  nuyina_data/202324050_005/nav/202324050_005.navtable
```

Expected: prints `wrote <N> rows to nuyina_data/202324050_005/nav/202324050_005.navtable` with N in the tens of thousands (one GGA fix roughly per second across the day). Then:

```bash
head -3 nuyina_data/202324050_005/nav/202324050_005.navtable
wc -l nuyina_data/202324050_005/nav/202324050_005.navtable
```

Expected: 3 whitespace-separated numeric fields per line, e.g. `-13395.461 -42.561002 148.492455` (a negative elapsed-seconds value near the top of the file is expected and correct — the day's nav log starts at 2024-06-17T00:00:00Z, which is before cast 005's 03:43:15Z start).

- [ ] **Step 6: Stage the already-local CODAS and LADCP data**

```bash
cp -r /home/peter_sha/sourcecode/Nuyina/nuyina_uhdas_codas/output/nuyina_202324050/os150nb/* \
  nuyina_data/202324050_005/codas/
ls nuyina_data/202324050_005/codas/contour/contour_xy.mat nuyina_data/202324050_005/codas/contour/contour_uv.mat
```

Expected: both files listed (copy succeeded). LADCP data is mounted directly from `nuyina_dev_env` in Task 2 — not copied here, since it's already in the right shape.

- [ ] **Step 7: Gitignore the staging directory**

Add to `.gitignore` (create the file if it doesn't already have this pattern; check first with `grep -q nuyina_data .gitignore || echo 'nuyina_data/' >> .gitignore`):

```
nuyina_data/
```

- [ ] **Step 8: Commit**

```bash
git add scripts/gngga_to_navtable.py .gitignore
git commit -m "feat: add GNGGA nav-table conversion script for real cast processing" -- scripts/gngga_to_navtable.py .gitignore
```

(The `nuyina_data/` staging directory itself is gitignored and never staged — only the script and the `.gitignore` entry are committed.)

---

### Task 2: Drive the webapp API to generate a real `set_cast_params.m`

**Files:**
- No files created or modified in this repo — this task only calls the already-shipped webapp's API against real data. Verification is the API responses and the generated `set_cast_params.m` inside the staging directory's `data/` folder (gitignored, not committed).

**Interfaces:**
- Consumes: `nuyina_data/202324050_005/{ctd,nav,codas,data}/` from Task 1, and `nuyina_dev_env/voyage_data/sample/adcp/ladcp/` (already on disk from prior work, path: `/home/peter_sha/sourcecode/Nuyina/nuyina_dev_env/voyage_data/sample/adcp/ladcp/`).
- Produces: `nuyina_data/202324050_005/data/set_cast_params.m` (referenced by Task 3), plus `nuyina_data/202324050_005/data/quick_convert/202324050_005.UNVALIDATED_QUICKCONVERT.cnv` and `nuyina_data/202324050_005/data/sadcp_convert/os150nb.SADCP.mat` (or whatever exact filename the SADCP-convert endpoint reports — read it from that call's real response, don't assume the name).

- [ ] **Step 1: Build the image if needed, then start the webapp container with all 5 mounts**

```bash
docker build -t ldeo-ix-octave:local -f Dockerfile .   # skip if already built (docker images | grep ldeo-ix-octave)
docker run -d --name ladcp_005 -p 8099:8080 \
  -v "$(pwd)/nuyina_data/202324050_005/data:/data" \
  -v "/home/peter_sha/sourcecode/Nuyina/nuyina_dev_env/voyage_data/sample/adcp/ladcp:/ladcp_data:ro" \
  -v "$(pwd)/nuyina_data/202324050_005/ctd:/ctd_data:ro" \
  -v "$(pwd)/nuyina_data/202324050_005/nav:/navigation_data:ro" \
  -v "$(pwd)/nuyina_data/202324050_005/codas:/codas_data:ro" \
  ldeo-ix-octave:local
sleep 3
curl -s http://localhost:8099/health
```

Expected: `{"status":"ok"}`.

- [ ] **Step 2: Confirm all 5 mounts are visible**

```bash
curl -s http://localhost:8099/api/mounts
```

Expected: `{"mounts":["codas","ctd","data","ladcp","nav"]}` (alphabetical order, all 5 present).

- [ ] **Step 3: Quick-convert cast 005's real CTD data**

```bash
curl -s -X POST http://localhost:8099/api/quick-convert/ctd \
  -H "Content-Type: application/json" \
  -d '{"hex_path":"202324050_005.hex","xmlcon_path":"202324050_005.XMLCON"}'
```

Expected: a JSON response containing `"ctd_path":"quick_convert/202324050_005.UNVALIDATED_QUICKCONVERT.cnv"`. If the response instead has an error, stop and read it — do not proceed to Step 4 with a missing CTD file.

- [ ] **Step 4: Preview the converted CTD file to confirm the real column layout**

```bash
curl -s "http://localhost:8099/api/preview/data?path=quick_convert/202324050_005.UNVALIDATED_QUICKCONVERT.cnv"
```

Expected (confirmed during design against this exact real file — if your output differs, use what the response actually says, not this expected value, since Quick-convert's `ctdam`-based output could in principle vary): `"header_lines": 283, "fields_per_line": 19`, and `"suggested_roles": {"pressure": 2, "temperature": 3, "salinity": 5, "time": 11, "lat": 18, "lon": 19}`.

- [ ] **Step 5: Convert the real CODAS OS150 output into a SADCP `.mat` file**

```bash
curl -s -X POST http://localhost:8099/api/sadcp/convert \
  -H "Content-Type: application/json" \
  -d '{"contour_dir":"contour"}'
```

Expected: a JSON response naming the produced `.mat` file's path under `sadcp_convert/`. Note the exact filename it reports — you'll need it verbatim in Step 7.

- [ ] **Step 6: Confirm LADCP auto-scan does not find cast 005 (expected, not a bug to fix)**

```bash
curl -s http://localhost:8099/api/ladcp/scan
```

Expected: `{"casts":[]}`. This is expected and correct, not a failure to investigate further — `webapp/ladcp_scan.py`'s filename regex (`^(?P<station>\d+)(?P<dir>[DU])L\d+\.\d+$`, matching LDEO_IX's own convention like `003DL000.000`) doesn't match Nuyina's real filenames (`2324050_005_down_ladcp.000`). Step 7 sets the LADCP filenames directly instead of relying on this scan.

- [ ] **Step 7: Create the cast session for cast 005 with every real field set**

```bash
curl -s -X POST http://localhost:8099/api/session/casts \
  -H "Content-Type: application/json" \
  -d '{
    "cast_name": "202324050_005",
    "ladcp_station": 5,
    "ladcp_cast": 5,
    "ladcpdo": "2324050_005_down_ladcp.000",
    "ladcpup": "2324050_005_up_ladcp.000",
    "ctd": "quick_convert/202324050_005.UNVALIDATED_QUICKCONVERT.cnv",
    "ctd_header_lines": 283,
    "ctd_fields_per_line": 19,
    "ctd_time_field": 11,
    "ctd_pressure_field": 2,
    "ctd_temperature_field": 3,
    "ctd_salinity_field": 5,
    "ctd_time_base": 0,
    "nav": "202324050_005.navtable",
    "nav_header_lines": 0,
    "nav_fields_per_line": 3,
    "nav_time_field": 1,
    "nav_lat_field": 2,
    "nav_lon_field": 3,
    "nav_time_base": 0,
    "sadcp": "REPLACE_WITH_STEP_5_RESPONSE_PATH",
    "time_start": [2024, 6, 17, 3, 43, 15],
    "checkpoints_steps": "1:16"
  }'
```

Replace `REPLACE_WITH_STEP_5_RESPONSE_PATH` with the exact path Step 5's response reported (relative to `/data`, e.g. `sadcp_convert/os150nb.SADCP.mat` — use the real value, not this guess). `ctd`/`nav` paths are relative to `/ctd_data`/`/navigation_data` respectively per the webapp's existing convention (confirmed by Step 3's request using a bare filename relative to `/ctd_data`); `ladcpdo`/`ladcpup` are relative to `/ladcp_data`.

Expected: HTTP 201 with the created cast entry echoed back, including a generated `id`.

- [ ] **Step 8: Generate `set_cast_params.m`**

```bash
curl -s -X POST http://localhost:8099/api/generate
cat nuyina_data/202324050_005/data/set_cast_params.m
```

Expected: a 200 response, and the printed file contains real values — `f.ladcpdo = '.../2324050_005_down_ladcp.000'`, `f.ctd = '.../202324050_005.UNVALIDATED_QUICKCONVERT.cnv'`, `f.nav = '.../202324050_005.navtable'`, `f.sadcp` pointing at the real converted `.mat` path, `p.time_start = [2024 6 17 3 43 15]` — not any empty or placeholder field. If any field is empty, the corresponding cast-session field in Step 7 was wrong or missing — fix and re-run Steps 7-8, don't proceed to Task 3 with an incomplete config.

- [ ] **Step 9: Leave the container running for Task 3** (no teardown here — Task 3 execs into this same container).

---

### Task 3: Run real LADCP processing and verify real output

**Files:**
- No files created or modified in this repo. Verification is the actual Octave run's output and the real saved result file.

**Interfaces:**
- Consumes: `nuyina_data/202324050_005/data/set_cast_params.m` from Task 2, and the running `ladcp_005` container from Task 2.
- Produces: nothing later tasks depend on — this is the last task in the plan.

- [ ] **Step 1: Run `process_cast(5, 1, 0)` for real inside the container**

  (Corrected from an earlier draft's `process_cast(5,1,2)`: `stop=2` pauses
  after **every** step forever with no auto-resume, not "stop after all
  steps" as the docstring comment misleadingly suggests — this caused a real
  11-minute stuck `keyboard()` busy-loop during this plan's own execution.
  See `.superpowers/sdd/2026-09-06-nuyina-ladcp-cast-processing/task-3-report.md`
  for the full story. `stop=0` is the correct value for an uninterrupted
  non-interactive run.)

```bash
docker exec -w /data ladcp_005 octave-cli --eval "process_cast(5,1,0)" 2>&1 | tee /tmp/process_cast_005_output.log
```

Expected: real Octave output progressing through all 17 steps listed in `ldeo_ix/process_cast.m`'s docstring (`LOAD LADCP DATA` through `SAVE OUTPUT`), with no Octave error (`error:` prefix) anywhere in the output. Real LADCP/CTD/nav processing prints real diagnostic numbers as it goes (e.g. "read N CTD scans", fix counts, calibration stats) — a completely silent run, or one that stops partway with no explicit step-17 completion, is a failure to investigate, not something to treat as "probably fine."

- [ ] **Step 2: Confirm the real output file exists and find its saved location**

`set_cast_params.m` was generated in Task 2 with `f.res` set by the webapp (check `nuyina_data/202324050_005/data/set_cast_params.m` for the actual `f.res` value it wrote):

```bash
grep "f.res" nuyina_data/202324050_005/data/set_cast_params.m
```

Then, using whatever path that prints (relative to `/data`):

```bash
find nuyina_data/202324050_005/data -newer nuyina_data/202324050_005/data/set_cast_params.m -type f
```

Expected: at least one new `.mat` file created after `set_cast_params.m`, under the directory `f.res` named.

- [ ] **Step 3: Inspect the real velocity output for genuine, non-empty values**

```bash
docker exec -w /data ladcp_005 octave-cli --eval "load('$(grep 'f.res' nuyina_data/202324050_005/data/set_cast_params.m | sed -E \"s/.*'([^']+)'.*/\1/\")/005.mat'); disp(size(dr.u)); disp([min(dr.u) max(dr.u)]); disp([min(dr.z) max(dr.z)])"
```

(The exact saved filename and variable names — `dr`, `dr.u`, `dr.z` — follow LDEO_IX's own convention documented in `process_cast.m`'s step 17/`ldeo_ix`'s own save logic; if this exact `load(...)` call errors because the real filename or variable differs, inspect the actual saved `.mat` file's contents directly with `whos -file <path>` inside the container and adjust — don't guess a filename that doesn't exist.)

Expected: `size(dr.u)` reports a real, non-trivial dimension (multiple depth bins, not `0x0` or `1x1`), the velocity range is a plausible ocean current magnitude (roughly `-2` to `2` m/s, not all-zero, not all-`NaN`), and the depth range (`dr.z`) spans a real fraction of the water column consistent with a genuine LADCP cast (tens to low thousands of metres, not `0` to `0`).

- [ ] **Step 4: Tear down the container**

```bash
docker rm -f ladcp_005
```

- [ ] **Step 5: Record what was found**

No code commit for this task (nothing in the repo changed) — but note in your final report: the real velocity range and depth range observed in Step 3, and whether the result looks physically sane for this cast (a first real, genuine data point for this whole effort, worth stating plainly either way — "looks physically reasonable" or "looks off, here's why" are both valid, useful findings; a report that only says "it ran without error" is missing the actual point of this task).
