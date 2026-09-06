# Generic Cast-Processing Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a vessel-agnostic `scripts/process_cast.sh` (+ docs) that any organization can use to drive the LDEO_IX_Octave webapp and `process_cast()` pipeline from local files, then use it to process two more real Nuyina LADCP casts (004 and 006 of voyage 202324050) via AAD-specific glue that never gets committed.

**Architecture:** A single bash+jq script drives the repo's existing `ldeo-ix-octave` Docker image through its already-shipped webapp API (Quick-convert, SADCP-convert, cast-session creation, `/api/generate`) and then the real `process_cast()` Octave run, taking every cast-specific fact from a `cast-config.json` file and a staging directory — no vessel identity anywhere in it. Real Nuyina/AAD fetch glue (rclone S3 pulls, `.hdr`-derived cast timing, CTD column-mapping discovery) lives in `nuyina_data/scripts/`, which is gitignored and never committed.

**Tech Stack:** bash, `jq`, `curl`, Docker, Python 3.12 (`.venv312`, for `gngga_to_navtable.py`'s tests and the uncommitted `derive_ctd_cast_config.py` helper), `rclone`.

## Global Constraints

- Work directly on branch `master` in `/home/peter_sha/sourcecode/Nuyina/LDEO_IX_Octave` — no git worktrees (this workspace's standing 2026-09-06 preference for solo development).
- No AI-authorship commit trailers on any commit (workspace-wide rule).
- The real Docker image is a single tag, `ldeo-ix-octave` (build with `docker build -t ldeo-ix-octave .` from the repo root). It has one `ENTRYPOINT` (`/opt/webapp/entrypoint.sh`) with two `CMD` modes: `serve` (default — starts `uvicorn webapp.main:app` on port 8080) and `octave-cli` (shifts and execs `octave-cli --no-gui "$@"`). There is no separate webapp image.
- The webapp has six mounts, via `webapp/config.py`: `data` (`/data`, read-write, `LDEO_DATA_DIR`), `ladcp` (`/ladcp_data`), `ctd` (`/ctd_data`), `sadcp` (`/sadcp_data`), `nav` (`/navigation_data`), `codas` (`/codas_data`). `sadcp` is for an already-converted SADCP `.mat`; `codas` is SADCP-convert's raw-CODAS-contour input. Never conflate the two.
- `CastEntry` (`webapp/models.py`) is the authoritative field-name contract for every JSON body posted to `/api/session/casts`. Its required fields (`webapp/validation.py:REQUIRED_FIELDS`) are `ladcpdo`, `ladcpup`, `ladcp_station`, `ladcp_cast`, `lat`, `lon`, `time_start`, `time_end`. `checkpoints_file`/`res_file` are auto-derived server-side from `cast_name` (`checkpoints/<cast_name>`, `V7/<cast_name>`) whenever they're omitted from the POST body — never set them explicitly.
- `ladcpdo`, `ladcpup`, `nav` are plain filenames relative to their own mount (`template_gen.py`'s `_mount_quote` prepends the mount path only when rendering `set_cast_params.m` — the API body itself never carries a mount-prefixed path). `ctd` and `sadcp` are `data`-relative paths, exactly as returned by `/api/quick-convert/ctd` (`ctd_path`) and `/api/sadcp/convert` (`sadcp_path`), or supplied directly if an organization already has converted files.
- **`drot` must never appear in any cast-config.json this plan produces, or in any body posted to `/api/session/casts`.** Per Andreas Thurnherr's own LDEO_IX manual: once real GPS nav is loaded, magnetic declination must be computed naturally by `process_cast`'s own step 3, not supplied manually (confirmed this session — supplying it early shifts a bottom-track QC threshold and produces a materially different, wrong solution).
- `nuyina_data/` is already gitignored. `nuyina_data/scripts/*.sh` and `nuyina_data/scripts/*.py` built by Task 5 are AAD/Nuyina-specific and **must never be committed** — before Task 5 is marked complete, `git status --short` must show them absent from the index (untracked-and-ignored, or simply not listed because `nuyina_data/` itself is ignored).
- Test baseline: `.venv312/bin/python -m pytest webapp/tests` currently passes 105/105, 0 skipped (per this repo's own `CLAUDE.md`). No task in this plan touches any `webapp/*.py` source file, so this must stay 105/105 throughout — re-run it after every task as a cheap regression guard.
- Tasks 4, 6, and 7 depend on real, live infrastructure (Docker, and for 6/7 also `rclone`/S3 and the real `nuyina_uhdas_codas`/`nuyina_dev_env` sibling repos being present with real data). If that infrastructure is unavailable when a task runs, the task must report BLOCKED with the real error encountered — never fabricate or template a plausible-looking result. (Precedent: the cast-005 plan's own final review found a fabricated-looking output block that didn't match a real command; the same scrutiny applies here — every "real output" quoted in a task report must be copy-pasted from an actual command this session ran, digests and all.)

---

### Task 1: Parameterize `scripts/gngga_to_navtable.py`

**Files:**
- Modify: `scripts/gngga_to_navtable.py`
- Test: `scripts/test_gngga_to_navtable.py` (new)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `convert(csv_path: str, out_path: str, cast_start: datetime) -> int` (now takes `cast_start` as a parameter instead of reading a module-level constant) and a `main(argv=None) -> int` CLI entry point taking a required `--cast-start` flag. Task 5's `fetch_cast_nav.sh` calls this script as `python3 scripts/gngga_to_navtable.py <csv> <out> --cast-start <iso8601>`.

The current script hardcodes `CAST_START = datetime(2024, 6, 17, 3, 43, 15, tzinfo=timezone.utc)` — cast 005's own start time. This was flagged by the cast-005 plan's final review as a real forward-risk: running it unmodified for another cast produces a perfectly valid-looking nav table on the wrong clock, silently.

- [ ] **Step 1: Write the failing tests**

```python
# scripts/test_gngga_to_navtable.py
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gngga_to_navtable import convert, nmea_to_decimal, _parse_cast_start

FIXTURE_CSV = """datetime,msg_id,gps_time_dgps_gga,latitude_dgps_gga,n_or_s_dgps_gga,longitude_dgps_gga,e_or_w_dgps_gga,fix_quality_dgps_gga,number_of_satellites_dgps_gga,horizontal_dilution_of_precision_dgps_gga,antenna_height_dgps_gga,geoid_height_above_reference_ellipsoid_dgps_gga,last_dgps_update_dgps_gga,differential_reference_station_id_dgps_gga
2024-06-17T00:44:58.000000Z,$GNGGA,004458.00,4233.6601,S,14829.5473,E,1,14,0.7,35.3,M,-4.7,M,,
2024-06-17T00:45:08.000000Z,$GNGGA,004508.00,4233.6620,S,14829.5480,E,1,14,0.7,35.3,M,-4.7,M,,
"""


def test_nmea_to_decimal_south_and_east_are_negative_and_positive():
    assert nmea_to_decimal("4233.6601", "S") == -(42 + 33.6601 / 60)
    assert nmea_to_decimal("14829.5473", "E") == 148 + 29.5473 / 60


def test_nmea_to_decimal_north_and_west():
    assert nmea_to_decimal("4233.6601", "N") == 42 + 33.6601 / 60
    assert nmea_to_decimal("14829.5473", "W") == -(148 + 29.5473 / 60)


def test_parse_cast_start_accepts_z_suffix():
    parsed = _parse_cast_start("2024-06-17T00:44:58Z")
    assert parsed == datetime(2024, 6, 17, 0, 44, 58, tzinfo=timezone.utc)


def test_convert_computes_elapsed_seconds_relative_to_cast_start(tmp_path):
    csv_path = tmp_path / "GNGGA_2024-06-17.csv"
    csv_path.write_text(FIXTURE_CSV)
    out_path = tmp_path / "out.navtable"
    cast_start = datetime(2024, 6, 17, 0, 44, 58, tzinfo=timezone.utc)

    rows_written = convert(str(csv_path), str(out_path), cast_start)

    assert rows_written == 2
    lines = out_path.read_text().splitlines()
    first_elapsed, first_lat, first_lon = (float(x) for x in lines[0].split())
    second_elapsed, _, _ = (float(x) for x in lines[1].split())
    assert first_elapsed == 0.0
    assert second_elapsed == 10.0
    assert round(first_lat, 6) == round(-(42 + 33.6601 / 60), 6)
    assert round(first_lon, 6) == round(148 + 29.5473 / 60, 6)


def test_convert_produces_different_elapsed_times_for_different_cast_starts(tmp_path):
    csv_path = tmp_path / "GNGGA_2024-06-17.csv"
    csv_path.write_text(FIXTURE_CSV)
    out_a = tmp_path / "a.navtable"
    out_b = tmp_path / "b.navtable"

    convert(str(csv_path), str(out_a), datetime(2024, 6, 17, 0, 44, 58, tzinfo=timezone.utc))
    convert(str(csv_path), str(out_b), datetime(2024, 6, 17, 3, 43, 15, tzinfo=timezone.utc))

    first_elapsed_a = float(out_a.read_text().splitlines()[0].split()[0])
    first_elapsed_b = float(out_b.read_text().splitlines()[0].split()[0])
    assert first_elapsed_a != first_elapsed_b


def test_cli_requires_cast_start_flag(tmp_path):
    csv_path = tmp_path / "GNGGA_2024-06-17.csv"
    csv_path.write_text(FIXTURE_CSV)
    out_path = tmp_path / "out.navtable"

    script = Path(__file__).resolve().parent / "gngga_to_navtable.py"
    result = subprocess.run(
        [sys.executable, str(script), str(csv_path), str(out_path)],
        capture_output=True, text=True,
    )

    assert result.returncode != 0
    assert "--cast-start" in result.stderr


def test_cli_writes_navtable_when_cast_start_given(tmp_path):
    csv_path = tmp_path / "GNGGA_2024-06-17.csv"
    csv_path.write_text(FIXTURE_CSV)
    out_path = tmp_path / "out.navtable"

    script = Path(__file__).resolve().parent / "gngga_to_navtable.py"
    result = subprocess.run(
        [sys.executable, str(script), str(csv_path), str(out_path),
         "--cast-start", "2024-06-17T00:44:58Z"],
        capture_output=True, text=True,
    )

    assert result.returncode == 0
    assert out_path.is_file()
    assert "wrote 2 rows" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv312/bin/python -m pytest scripts/test_gngga_to_navtable.py -v`
Expected: collection error or `ImportError: cannot import name '_parse_cast_start'` (the current script has no such function, and `convert()`'s signature doesn't accept `cast_start`).

- [ ] **Step 3: Rewrite `scripts/gngga_to_navtable.py`**

```python
#!/usr/bin/env python3
"""Convert a Kongsberg GNGGA proc/csv extract (comma-delimited, ISO-8601
timestamp) into the plain whitespace-delimited, all-numeric table
ldeo_ix/loadnav.m's fscanf-based reader (and the LDEO_IX_Octave webapp's
generic column-mapper, which shares the same whitespace/all-numeric
assumption) require: elapsed_seconds lat_decimal_degrees lon_decimal_degrees,
one row per fix, no header.

elapsed_seconds is relative to --cast-start, which must be set to the exact
same value used for the cast's time_start field in the cast-config.json /
set_cast_params.m -- loadctd.m and loadnav.m both convert their own
elapsed-seconds columns to an absolute Julian date via `p.time_start`, so a
mismatch here would put the CTD and nav time series on different absolute
clocks.

This is AAD's own converter for its own Kongsberg GNGGA proc/csv export
format -- see docs/vessel-data-preparation.md for why every organization
needs its own equivalent rather than reusing this one verbatim.
"""
import argparse
import csv
import sys
from datetime import datetime, timezone


def nmea_to_decimal(value: str, hemisphere: str) -> float:
    """Convert NMEA ddmm.mmmm (or dddmm.mmmm for longitude) to decimal degrees."""
    raw = float(value)
    degrees = int(raw / 100)
    minutes = raw - degrees * 100
    decimal = degrees + minutes / 60
    if hemisphere in ("S", "W"):
        decimal = -decimal
    return decimal


def convert(csv_path: str, out_path: str, cast_start: datetime) -> int:
    rows_written = 0
    with open(csv_path, newline="") as fh, open(out_path, "w") as out:
        reader = csv.DictReader(fh)
        for row in reader:
            timestamp = datetime.fromisoformat(row["datetime"].replace("Z", "+00:00"))
            elapsed_seconds = (timestamp - cast_start).total_seconds()
            lat = nmea_to_decimal(row["latitude_dgps_gga"], row["n_or_s_dgps_gga"])
            lon = nmea_to_decimal(row["longitude_dgps_gga"], row["e_or_w_dgps_gga"])
            out.write(f"{elapsed_seconds:.3f} {lat:.6f} {lon:.6f}\n")
            rows_written += 1
    return rows_written


def _parse_cast_start(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", help="input GNGGA proc/csv extract")
    parser.add_argument("out_path", help="output plain-numeric nav table")
    parser.add_argument(
        "--cast-start",
        required=True,
        type=_parse_cast_start,
        help="cast start time, ISO-8601 (e.g. 2024-06-17T03:43:15Z) -- must match this "
             "cast's time_start in cast-config.json exactly",
    )
    args = parser.parse_args(argv)
    count = convert(args.csv_path, args.out_path, args.cast_start)
    print(f"wrote {count} rows to {args.out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv312/bin/python -m pytest scripts/test_gngga_to_navtable.py -v`
Expected: 7 passed.

- [ ] **Step 5: Confirm the webapp test suite is unaffected**

Run: `.venv312/bin/python -m pytest webapp/tests`
Expected: 105 passed (unchanged — this task touches no `webapp/` file).

- [ ] **Step 6: Commit**

```bash
git add scripts/gngga_to_navtable.py scripts/test_gngga_to_navtable.py
git commit -m "$(cat <<'EOF'
fix: parameterize gngga_to_navtable.py's cast-start time

Replaces the hardcoded cast-005 constant with a required --cast-start
CLI flag, closing the forward-risk the cast-005 plan's final review
flagged for the next cast that reuses this script.
EOF
)"
```

---

### Task 2: `scripts/process_cast.sh` — the generic driver script

**Files:**
- Create: `scripts/process_cast.sh`

**Interfaces:**
- Consumes: nothing from other tasks (uses only the webapp's already-shipped API and the repo's already-built `ldeo-ix-octave` image).
- Produces: `scripts/process_cast.sh <staging-dir> <cast-config.json> [image-tag]`, exit code 0 on success. Task 4 (dry run), Task 6, and Task 7 all invoke this exact CLI. The `cast-config.json` schema this script reads is fixed here and is the interface Task 5's Nuyina-specific scripts must produce:
  - Required: `station` (int), `cast_name` (str), `ladcpdo`, `ladcpup` (str, relative to the `ladcp` mount), `nav` (str, relative to the `nav` mount), `lat`, `lon` (numbers), `time_start`, `time_end` (six-element `[Y,M,D,h,m,s]` arrays).
  - CTD: either `ctd_hex` + `ctd_xmlcon` (relative to the `ctd` mount, triggers Quick-convert) or `ctd_cnv` (relative to the `ctd` mount, an already-converted file, passed straight through as-is — note this is a real gap: `ctd_cnv`, unlike `ctd_hex`/`ctd_xmlcon`, is never mount-prefixed or validated by this script, since `webapp/models.py`'s `ctd` field is `data`-relative for Quick-convert output but the webapp has no endpoint that accepts an arbitrary `ctd`-mount path directly — an organization using `ctd_cnv` must pre-copy their converted file into the `data/` staging subdirectory themselves and set `ctd_cnv` to its `data`-relative path; document this plainly in Task 3's guide).
  - CTD column mapping (all optional, passed straight through to the cast body when present): `ctd_header_lines`, `ctd_fields_per_line`, `ctd_time_field`, `ctd_pressure_field`, `ctd_temperature_field`, `ctd_salinity_field`, `ctd_badvals`, `ctd_time_base`.
  - Nav column mapping (all optional, passed straight through): `nav_header_lines`, `nav_fields_per_line`, `nav_time_field`, `nav_lat_field`, `nav_lon_field`, `nav_time_base`, `nav_error`.
  - SADCP (optional, mutually exclusive): `sadcp_contour_dir` (relative to the `codas` mount, triggers SADCP-convert) or `sadcp_mat_path` (relative to the `sadcp` mount, passed straight through).
  - `btrk_mode`, `btrk_used` (optional, passed straight through).
  - `drot` is rejected outright if present (see Global Constraints).

No test suite is possible for this script in isolation (it needs Docker, a built image, and the webapp actually running) — `bash -n` is the only static check; real behavioral verification is Task 4.

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# Drives a single LDEO_IX_Octave cast end-to-end: starts the repo's own
# ldeo-ix-octave image (serve mode) against a staging directory, converts
# CTD/SADCP inputs if the cast config asks for it, creates the cast
# session, generates set_cast_params.m, then runs the real 17-step
# process_cast(...) pipeline (octave-cli mode).
#
# No vessel/organization-specific code belongs in this file -- see
# docs/vessel-data-preparation.md for the input contract and how to write
# your own fetch/prep script that feeds it.
#
# Usage: scripts/process_cast.sh <staging-dir> <cast-config.json> [image-tag]
set -euo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  echo "usage: $0 <staging-dir> <cast-config.json> [image-tag]" >&2
  exit 1
fi

STAGING_DIR=$(cd "$1" && pwd)
CONFIG_DIR=$(cd "$(dirname "$2")" && pwd)
CONFIG_FILE="$CONFIG_DIR/$(basename "$2")"
IMAGE_TAG="${3:-ldeo-ix-octave}"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "error: cast config not found: $CONFIG_FILE" >&2
  exit 1
fi

for required_dir in ctd nav data ladcp; do
  if [ ! -d "$STAGING_DIR/$required_dir" ]; then
    echo "error: staging directory is missing required subdirectory: $required_dir/" >&2
    exit 1
  fi
done

HAS_SADCP_CONTOUR=$(jq -r 'has("sadcp_contour_dir")' "$CONFIG_FILE")
HAS_SADCP_MAT=$(jq -r 'has("sadcp_mat_path")' "$CONFIG_FILE")
if [ "$HAS_SADCP_CONTOUR" = "true" ] && [ "$HAS_SADCP_MAT" = "true" ]; then
  echo "error: cast config sets both sadcp_contour_dir and sadcp_mat_path -- only one is allowed" >&2
  exit 1
fi
if [ "$HAS_SADCP_CONTOUR" = "true" ] && [ ! -d "$STAGING_DIR/codas" ]; then
  echo "error: cast config sets sadcp_contour_dir but staging directory has no codas/ subdirectory" >&2
  exit 1
fi
if [ "$HAS_SADCP_MAT" = "true" ] && [ ! -d "$STAGING_DIR/sadcp" ]; then
  echo "error: cast config sets sadcp_mat_path but staging directory has no sadcp/ subdirectory" >&2
  exit 1
fi

if [ "$(jq -r 'has("drot")' "$CONFIG_FILE")" = "true" ]; then
  echo "error: cast config sets drot -- this script never sets declination manually (real GPS nav means it must be computed by process_cast's own step 3; see docs/vessel-data-preparation.md)" >&2
  exit 1
fi

# A stale session left over from a previous run of this staging directory
# would add a second cast to the same set_cast_params.m instead of
# replacing the first -- every invocation of this script is scoped to
# exactly one cast.
rm -f "$STAGING_DIR/data/.cruise_intake_session.json"

MOUNT_ARGS=(
  -v "$STAGING_DIR/data:/data"
  -v "$STAGING_DIR/ladcp:/ladcp_data"
  -v "$STAGING_DIR/ctd:/ctd_data"
  -v "$STAGING_DIR/nav:/navigation_data"
)
if [ "$HAS_SADCP_CONTOUR" = "true" ]; then
  MOUNT_ARGS+=(-v "$STAGING_DIR/codas:/codas_data")
fi
if [ "$HAS_SADCP_MAT" = "true" ]; then
  MOUNT_ARGS+=(-v "$STAGING_DIR/sadcp:/sadcp_data")
fi

echo "starting $IMAGE_TAG (serve mode) ..."
CONTAINER_ID=$(docker run -d --rm -p 0:8080 "${MOUNT_ARGS[@]}" "$IMAGE_TAG")
cleanup() {
  docker stop "$CONTAINER_ID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

HOST_PORT=$(docker port "$CONTAINER_ID" 8080/tcp | head -n1 | cut -d: -f2)
BASE_URL="http://localhost:${HOST_PORT}"

echo "waiting for $BASE_URL/health ..."
HEALTHY=false
for _ in $(seq 1 30); do
  if curl -sf "$BASE_URL/health" >/dev/null 2>&1; then
    HEALTHY=true
    break
  fi
  sleep 1
done
if [ "$HEALTHY" != "true" ]; then
  echo "error: webapp never became healthy at $BASE_URL/health" >&2
  docker logs "$CONTAINER_ID" >&2 || true
  exit 1
fi

echo "mounts available: $(curl -sf "$BASE_URL/api/mounts")"

HTTP_CODE=""
http_post() {
  local path="$1" body="$2"
  local response
  response=$(curl -sS -w '\n%{http_code}' -X POST "$BASE_URL$path" \
    -H 'Content-Type: application/json' -d "$body")
  HTTP_CODE=$(echo "$response" | tail -n1)
  echo "$response" | sed '$d'
}

if [ "$(jq -r 'has("ctd_hex")' "$CONFIG_FILE")" = "true" ]; then
  HEX_PATH=$(jq -r '.ctd_hex' "$CONFIG_FILE")
  XMLCON_PATH=$(jq -r '.ctd_xmlcon' "$CONFIG_FILE")
  echo "quick-converting $HEX_PATH ..."
  BODY=$(jq -n --arg hex "$HEX_PATH" --arg xmlcon "$XMLCON_PATH" '{hex_path: $hex, xmlcon_path: $xmlcon}')
  RESPONSE=$(http_post "/api/quick-convert/ctd" "$BODY")
  if [ "$HTTP_CODE" != "200" ]; then
    echo "error: quick-convert failed ($HTTP_CODE): $RESPONSE" >&2
    exit 1
  fi
  CTD_PATH=$(echo "$RESPONSE" | jq -r '.ctd_path')
else
  CTD_PATH=$(jq -r '.ctd_cnv' "$CONFIG_FILE")
fi

SADCP_PATH=""
if [ "$HAS_SADCP_CONTOUR" = "true" ]; then
  CONTOUR_DIR=$(jq -r '.sadcp_contour_dir' "$CONFIG_FILE")
  echo "converting SADCP contour $CONTOUR_DIR ..."
  BODY=$(jq -n --arg dir "$CONTOUR_DIR" '{contour_dir: $dir}')
  RESPONSE=$(http_post "/api/sadcp/convert" "$BODY")
  if [ "$HTTP_CODE" != "200" ]; then
    echo "error: sadcp-convert failed ($HTTP_CODE): $RESPONSE" >&2
    exit 1
  fi
  SADCP_PATH=$(echo "$RESPONSE" | jq -r '.sadcp_path')
elif [ "$HAS_SADCP_MAT" = "true" ]; then
  SADCP_PATH=$(jq -r '.sadcp_mat_path' "$CONFIG_FILE")
fi

PASSTHROUGH_KEYS='["ctd_header_lines","ctd_fields_per_line","ctd_time_field","ctd_pressure_field",
  "ctd_temperature_field","ctd_salinity_field","ctd_badvals","ctd_time_base",
  "nav_header_lines","nav_fields_per_line","nav_time_field","nav_lat_field",
  "nav_lon_field","nav_time_base","nav_error","btrk_mode","btrk_used"]'

CAST_BODY=$(jq --argjson allowed "$PASSTHROUGH_KEYS" '
  {
    cast_name: .cast_name,
    ladcp_station: .station,
    ladcp_cast: .station,
    ladcpdo: .ladcpdo,
    ladcpup: .ladcpup,
    nav: .nav,
    lat: .lat,
    lon: .lon,
    time_start: .time_start,
    time_end: .time_end
  }
  + (to_entries | map(select(.key as $k | $allowed | index($k))) | from_entries)
' "$CONFIG_FILE")

CAST_BODY=$(echo "$CAST_BODY" | jq --arg ctd "$CTD_PATH" '. + {ctd: $ctd}')
if [ -n "$SADCP_PATH" ]; then
  CAST_BODY=$(echo "$CAST_BODY" | jq --arg sadcp "$SADCP_PATH" '. + {sadcp: $sadcp}')
fi

echo "creating cast session entry ..."
RESPONSE=$(http_post "/api/session/casts" "$CAST_BODY")
if [ "$HTTP_CODE" != "201" ]; then
  echo "error: creating cast failed ($HTTP_CODE): $RESPONSE" >&2
  exit 1
fi

echo "generating set_cast_params.m ..."
RESPONSE=$(http_post "/api/generate" "{}")
if [ "$HTTP_CODE" != "200" ]; then
  echo "error: /api/generate failed ($HTTP_CODE): $RESPONSE" >&2
  exit 1
fi
echo "$RESPONSE"

STATION=$(jq -r '.station' "$CONFIG_FILE")
CAST_NAME=$(jq -r '.cast_name' "$CONFIG_FILE")

echo "stopping webapp container ..."
docker stop "$CONTAINER_ID" >/dev/null
trap - EXIT

echo "running process_cast($STATION,1,0) ..."
docker run --rm -v "$STAGING_DIR/data:/data" "$IMAGE_TAG" octave-cli --eval "process_cast($STATION,1,0)"

echo "done."
echo "saved state / diary base path: $STAGING_DIR/data/V7/$CAST_NAME (process_cast's own save/diary conventions determine the exact suffixes)"
```

- [ ] **Step 2: Syntax-check the script**

Run: `bash -n scripts/process_cast.sh`
Expected: no output, exit code 0.

- [ ] **Step 3: Make it executable and confirm the webapp test suite is still unaffected**

```bash
chmod +x scripts/process_cast.sh
.venv312/bin/python -m pytest webapp/tests
```
Expected: 105 passed (this task adds a new file but touches no `webapp/` source).

- [ ] **Step 4: Commit**

```bash
git add scripts/process_cast.sh
git commit -m "$(cat <<'EOF'
feat: add generic scripts/process_cast.sh cast-processing driver

Drives the existing webapp API (Quick-convert, SADCP-convert, cast
session, /api/generate) and the real process_cast() Octave run from a
staging directory and cast-config.json, with no vessel-specific code.
Verified against a real cast in the next task.
EOF
)"
```

---

### Task 3: `docs/vessel-data-preparation.md`

**Files:**
- Create: `docs/vessel-data-preparation.md`
- Modify: `README.md` (one new line linking to it, in the "Usage" or top-of-file file-listing section, following the existing bullet-list style used for `webapp/`)

**Interfaces:**
- Consumes: the `scripts/process_cast.sh` CLI and cast-config.json schema fixed in Task 2.
- Produces: nothing consumed by later tasks — this is documentation only.

No automated test applies to a markdown file; verification is a careful read plus confirming the linked file paths and command examples are accurate against Task 2's real script.

- [ ] **Step 1: Write the document**

```markdown
# Preparing Your Vessel's Data for `process_cast.sh`

`scripts/process_cast.sh` drives this repo's webapp + `process_cast()` pipeline for one
LADCP cast, given local files staged in a fixed layout and a `cast-config.json` describing
them. It has no knowledge of any particular vessel, instrument brand, or data archive — that
part is up to you. This page describes the contract your own fetch/prep script must satisfy.

## Staging layout

Create a directory (anywhere on disk) with these subdirectories:

| Subdirectory | Mounted at | Contents |
|---|---|---|
| `ctd/` | `/ctd_data` (read-only) | Raw Sea-Bird `.hex`+`.XMLCON`, or an already-converted file (see CTD below) |
| `nav/` | `/navigation_data` (read-only) | Your prepared nav table (see Navigation below) |
| `ladcp/` | `/ladcp_data` (read-only) | The cast's raw LADCP down/up files |
| `data/` | `/data` (read-write) | Starts empty; becomes the working directory |
| `codas/` | `/codas_data` (read-only, optional) | A CODAS `contour/` directory, if you want SADCP-convert to run |
| `sadcp/` | `/sadcp_data` (read-only, optional) | An already-converted SADCP `.mat`, if you have one and want to skip SADCP-convert |

Only create `codas/`/`sadcp/` if you're using one of them — `scripts/process_cast.sh` only
mounts what your `cast-config.json` actually asks for.

## CTD

Two options:

- **Raw Sea-Bird `.hex` + `.XMLCON`** (most common if you don't already run Sea-Bird's own SBE
  Data Processing software): set `ctd_hex`/`ctd_xmlcon` in your cast-config.json (paths relative
  to `ctd/`). The script runs Quick-convert for you. Quick-convert's output is explicitly marked
  `UNVALIDATED_QUICKCONVERT` — it hasn't been checked against Sea-Bird's own reference conversion
  software, so treat it as a real but unvalidated conversion, not a substitute for SBE Data
  Processing if you have access to it.
- **Already-converted `.cnv`**: copy it into your staging directory's `data/` subdirectory
  yourself, then set `ctd_cnv` to its path relative to `data/` (e.g. `"my_cast.cnv"` if you
  copied it to `data/my_cast.cnv`). The script passes this straight through without touching it.

Either way, you also need the CTD column-mapping fields: `ctd_header_lines`,
`ctd_fields_per_line`, `ctd_time_field`, `ctd_pressure_field`, `ctd_temperature_field`,
`ctd_salinity_field` (all 1-indexed column positions, matching Octave/MATLAB convention),
`ctd_badvals` (the numeric flag your file uses for missing data — Sea-Bird files commonly use
`-9e99`), and `ctd_time_base` (usually `0`). If you don't already know these, run the webapp's
web form once against your first cast — its file preview/column-mapping UI shows you these
values interactively — and reuse them for the rest of that instrument's casts.

## Navigation — the one step you'll need to build yourself

This is the part that's genuinely different for every organization. `process_cast.sh` (and the
webapp underneath it) requires your nav data as a **plain whitespace-delimited, all-numeric**
table, one row per fix, no header:

```
elapsed_seconds latitude_decimal_degrees longitude_decimal_degrees
0.000 -42.559128 148.490637
10.021 -42.559140 148.490655
```

`elapsed_seconds` must be relative to the same cast start time you put in `time_start`.
Latitude/longitude must already be in decimal degrees (not NMEA `ddmm.mmmm`).

Whatever format your vessel's nav logging actually produces — NMEA sentences, a CSV export, a
proprietary logger dump — you need a small one-off script that reads it and writes this table.
`scripts/gngga_to_navtable.py` in this repo is AAD's own converter, for AAD's own Kongsberg
GNGGA proc/csv export format: it's a real, complete example of the shape such a converter takes
(parse timestamps, convert NMEA degrees/minutes to decimal, compute elapsed seconds relative to
a `--cast-start` you pass on the command line) — but its column names and input format are
specific to AAD's own pipeline. Yours will look different; don't try to reuse it verbatim unless
your raw nav data happens to be in exactly the same shape.

Once you have your nav table, set `nav` in your cast-config.json to its path relative to
`nav/`, plus `nav_header_lines` (`0` for a header-free table like the one above),
`nav_fields_per_line` (`3`), `nav_time_field`, `nav_lat_field`, `nav_lon_field` (`1`, `2`, `3`
for the column order shown above).

## SADCP (optional)

If you have vessel-mounted ADCP (VM-ADCP/SADCP) data already processed through UHDAS+CODAS, its
`contour/` directory (containing `contour_xy.mat` and `contour_uv.mat`) is exactly what
SADCP-convert expects — no special preparation needed. Set `sadcp_contour_dir` in your
cast-config.json to that directory's path relative to `codas/`.

If you don't run CODAS but already have a converted SADCP `.mat` file some other way, copy it
into `sadcp/` and set `sadcp_mat_path` instead.

If you have no SADCP data at all, omit both — LADCP processing works without a SADCP reference,
just with less independent quality control on the final solution.

## Magnetic declination — don't set it manually

`cast-config.json` has no `drot` field, and `scripts/process_cast.sh` rejects a config that sets
one. This is deliberate: per Andreas Thurnherr's own LDEO_IX manual, once real GPS navigation
data is loaded, magnetic declination must be left to compute naturally in `process_cast`'s own
processing step 3 — supplying it manually changes the timing of a bottom-track quality-control
threshold and produces a materially different, incorrect solution. If your instrument's own
software reports a declination value, don't put it in your cast-config.json; the pipeline
computes its own from your real nav data.

## Putting it together: `cast-config.json`

```json
{
  "station": 12,
  "cast_name": "myvessel_012",
  "ladcpdo": "myvessel_012_down.000",
  "ladcpup": "myvessel_012_up.000",
  "ctd_hex": "myvessel_012.hex",
  "ctd_xmlcon": "myvessel_012.XMLCON",
  "ctd_header_lines": 283,
  "ctd_fields_per_line": 19,
  "ctd_time_field": 11,
  "ctd_pressure_field": 2,
  "ctd_temperature_field": 3,
  "ctd_salinity_field": 5,
  "ctd_badvals": -9e99,
  "ctd_time_base": 0,
  "nav": "myvessel_012.navtable",
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

`station` becomes both `process_cast`'s station argument and the cast's `ladcp_station`/
`ladcp_cast` fields. `time_start`/`time_end` are `[year, month, day, hour, minute, second]`,
matching `process_cast`'s own date-vector convention (seconds may have a fractional part).

Run it:

```bash
docker build -t ldeo-ix-octave .   # once, or whenever the image changes
scripts/process_cast.sh /path/to/your/staging-dir /path/to/cast-config.json
```

## Writing your own vessel-specific fetch script

The usual pattern:

1. Fetch your raw LADCP/CTD/nav/SADCP data by whatever means your organization uses (an S3
   bucket, a shipboard NAS, a manual USB transfer — this repo has no opinion).
2. Convert your raw nav data to the plain-numeric contract above.
3. Stage everything into the layout at the top of this page.
4. Write a `cast-config.json` like the one above.
5. Call `scripts/process_cast.sh <staging-dir> <cast-config.json>`.

AAD's own such script exists (it fetches from AAD's private shore-side S3 bucket) but
deliberately isn't part of this repo — it's 100% specific to AAD's own archive and credentials,
and bundling it here would make this repo work well for one organization at the expense of being
usable by anyone else. Yours will look different, and that's the point.
```

- [ ] **Step 2: Link it from README.md**

Read `README.md`'s file-listing bullet list near the top (the one starting `- `webapp/` — the
web intake form...`) and add one line immediately after it:

```markdown
- `docs/vessel-data-preparation.md` — how to prepare your own vessel's data for
  `scripts/process_cast.sh` if you're not AAD.
```

- [ ] **Step 3: Confirm the webapp test suite is still unaffected**

Run: `.venv312/bin/python -m pytest webapp/tests`
Expected: 105 passed.

- [ ] **Step 4: Commit**

```bash
git add docs/vessel-data-preparation.md README.md
git commit -m "$(cat <<'EOF'
docs: add vessel data preparation guide for process_cast.sh

Documents the staging layout, CTD/nav/SADCP input contracts, the
declination guidance, and how another organization would write its own
fetch script to feed the generic driver.
EOF
)"
```

---

### Task 4: Dry-run verification — reproduce cast 005's known-good result

**Files:**
- Create (untracked, not committed — this is a throwaway verification artifact): a temporary `cast-config.json` for the dry run, either at `/tmp` or directly at `nuyina_data/202324050_005/cast-config.json` (gitignored either way since it's under `nuyina_data/`)

**Interfaces:**
- Consumes: `scripts/process_cast.sh` from Task 2.
- Produces: nothing consumed by later tasks — this is a verification gate proving Task 2's script actually works against real data before Task 5/6/7 build on it.

This task requires Docker and the already-built `ldeo-ix-octave` image, and reuses the **existing** `nuyina_data/202324050_005/` staging directory from the earlier cast-005 processing session — do not recreate it.

- [ ] **Step 1: Build the image if not already built**

```bash
docker build -t ldeo-ix-octave .
```

- [ ] **Step 2: Write the real cast-005 cast-config.json**

These values are copied verbatim from `nuyina_data/202324050_005/data/set_cast_params.m`, the
real, already-generated file from the earlier cast-005 processing session:

```bash
cat > nuyina_data/202324050_005/cast-config.json <<'EOF'
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
EOF
```

Note `sadcp_contour_dir` is `"contour"`, not `"os150nb/contour"` — the real staged
`nuyina_data/202324050_005/codas/` directory has `contour/` directly under it (confirm with
`ls nuyina_data/202324050_005/codas/`), not nested under an `os150nb/` subdirectory.

- [ ] **Step 3: Run it**

```bash
scripts/process_cast.sh nuyina_data/202324050_005 nuyina_data/202324050_005/cast-config.json
```

Expected: exits 0, prints `generating set_cast_params.m ...` then the real `/api/generate`
response, then the real `process_cast(5,1,0) ...` Octave run to completion with no error.

- [ ] **Step 4: Inspect the real output and compare against the known-good numbers**

```bash
docker run --rm -v "$(pwd)/nuyina_data/202324050_005/data:/data" ldeo-ix-octave \
  octave-cli --eval "load /data/V7/202324050_005.mat; disp(dr.u([1 end])); disp(dr.v([1 end])); disp(p.drot)"
```

(If the variable names inside the saved `.mat` differ from `dr.u`/`dr.v`/`p.drot`, inspect with
`whos -file /data/V7/202324050_005.mat` first and adjust the `load`/`disp` accordingly — the
task report must show the real command that worked, not this exact guess if it needed
adjusting.)

Expected, matching `HANDOVER.md`'s already-recorded real result for this cast:
`u≈[-0.071990, 0.166196]`, `v≈[-0.087944, 0.265295]`, `drot≈15.0572`. A match (within floating-
point rounding) confirms `scripts/process_cast.sh` reproduces the already-verified real pipeline
correctly. A mismatch is a real bug in `scripts/process_cast.sh` — fix it (most likely culprit:
a field the jq transform in Task 2 handles differently than the original manual `curl` sequence
did) and re-run this step before proceeding to Task 5.

- [ ] **Step 5: Record the real captured output**

The task report must quote the actual terminal output of Steps 3 and 4 verbatim — not a
reformatted or idealized version of it.

No commit for this task — it's a verification run against an already-committed script, and its
only artifact (`nuyina_data/202324050_005/cast-config.json`) is gitignored.

---

### Task 5: AAD/Nuyina-specific fetch & config-generation scripts (NOT committed)

**Files (all created under `nuyina_data/scripts/`, gitignored, none committed):**
- Create: `nuyina_data/scripts/fetch_cast_ctd.sh`
- Create: `nuyina_data/scripts/fetch_cast_nav.sh`
- Create: `nuyina_data/scripts/derive_ctd_cast_config.py`
- Create: `nuyina_data/scripts/process_nuyina_cast.sh`

**Interfaces:**
- Consumes: `scripts/process_cast.sh` (Task 2), `scripts/gngga_to_navtable.py --cast-start` (Task 1).
- Produces: `nuyina_data/scripts/process_nuyina_cast.sh <voyage> <cast>` (e.g. `process_nuyina_cast.sh 202324050 004`) — the single entry point Tasks 6 and 7 call.

Real, already-confirmed facts this task's scripts rely on:

- CTD raw files live at `aadckingston:$S3_BUCKET/<voyage>/ctd/ctd_seabird/raw/seasave/<voyage>_<cast>.{hex,XMLCON,hdr,bl}` (confirmed via a real `rclone lsf` against the live bucket this session: casts `004`, `005`, `006` all present under `202324050`).
- Nav data lives at `aadckingston:$S3_BUCKET/<voyage>/dgps/proc/csv/GNGGA/GNGGA_<YYYY-MM-DD>.csv` — **not** under `raw/`; `raw/` holds the actual Kongsberg sentence text files, but AAD's own pipeline already extracts a per-message-type CSV under `proc/csv/GNGGA/`, which is exactly what `gngga_to_navtable.py` already consumes (confirmed via a real `rclone lsf` this session).
- Each `.hdr` file's `System UpLoad Time = <Mon> <DD> <YYYY> <HH:MM:SS>` line is the cast's real start time. Confirmed real values this session: cast 004 = `2024-06-17T00:44:58Z`, cast 005 = `2024-06-17T03:43:15Z` (already known), cast 006 = `2024-06-17T08:08:07Z` — all three fall on the same day, so `GNGGA_2024-06-17.csv` covers all three (no midnight-crossing case to handle for this voyage, though the scripts below still derive the date generically rather than hardcoding `2024-06-17`).
- LADCP raw files for all three casts already exist locally at
  `../nuyina_dev_env/voyage_data/sample/adcp/ladcp/<voyage-without-leading-"20">_<cast>_{down,up}_ladcp.000`
  (confirmed real filenames this session, e.g. `2324050_004_down_ladcp.000` for voyage
  `202324050` cast `004` — note the filename drops the voyage ID's leading `"20"`).
- SADCP CODAS contour output for the whole voyage already exists locally at
  `../nuyina_uhdas_codas/output/nuyina_<voyage>/os150nb/contour/{contour_xy,contour_uv}.mat`
  (one dataset covers every cast of the voyage).
- The real CTD column layout for this voyage's instrument (confirmed against the real,
  already-converted cast-005 `.cnv` this session): `# name 0 = depSM`, `1 = prDM`, `2 = t090C`,
  `3 = t190C`, `4 = sal00`, ..., `10 = timeS`, ..., 19 columns total, 283 header lines. Because
  the exact header-line count and column layout are properties of the specific hex file (not
  guaranteed identical across casts even on the same instrument), `derive_ctd_cast_config.py`
  below re-derives them for each cast rather than hardcoding cast 005's numbers.

- [ ] **Step 1: `nuyina_data/scripts/fetch_cast_ctd.sh`**

```bash
mkdir -p nuyina_data/scripts
cat > nuyina_data/scripts/fetch_cast_ctd.sh <<'SCRIPT_EOF'
#!/usr/bin/env bash
# AAD/Nuyina-specific: rclone-pulls one cast's raw CTD files from the
# aadc-kingston shore bucket. NOT part of the public repo -- see
# docs/superpowers/specs/2026-09-06-generic-cast-processing-script-design.md.
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: $0 <voyage> <cast>  (e.g. $0 202324050 004)" >&2
  exit 1
fi
VOYAGE="$1"
CAST="$2"
CAST_NAME="${VOYAGE}_${CAST}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LDEO_REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
NUYINA_ROOT="$(cd "$LDEO_REPO_ROOT/.." && pwd)"
ENV_FILE="$NUYINA_ROOT/.env"
STAGING_DIR="$LDEO_REPO_ROOT/nuyina_data/$CAST_NAME"

if [ ! -f "$ENV_FILE" ]; then
  echo "fetch_cast_ctd: workspace .env not found at $ENV_FILE" >&2
  exit 1
fi
for var in S3_HOST S3_ACCESS_KEY S3_SECRET_KEY S3_BUCKET; do
  value="$(grep -E "^${var}=" "$ENV_FILE" | tail -1 | cut -d= -f2-)"
  if [ -z "$value" ]; then
    echo "fetch_cast_ctd: $var not set in $ENV_FILE" >&2
    exit 1
  fi
  printf -v "$var" '%s' "$value"
done

export RCLONE_CONFIG_AADCKINGSTON_TYPE=s3
export RCLONE_CONFIG_AADCKINGSTON_PROVIDER=Other
export RCLONE_CONFIG_AADCKINGSTON_ENDPOINT="$S3_HOST"
export RCLONE_CONFIG_AADCKINGSTON_ACCESS_KEY_ID="$S3_ACCESS_KEY"
export RCLONE_CONFIG_AADCKINGSTON_SECRET_ACCESS_KEY="$S3_SECRET_KEY"

mkdir -p "$STAGING_DIR/ctd"
SRC="aadckingston:$S3_BUCKET/$VOYAGE/ctd/ctd_seabird/raw/seasave"
TMP="$(mktemp -d)"

for ext in hex XMLCON hdr bl; do
  rclone copyto "$SRC/${CAST_NAME}.${ext}" "$TMP/${CAST_NAME}.${ext}"
done

for ext in hex XMLCON hdr bl; do
  cp "$TMP/${CAST_NAME}.${ext}" "$STAGING_DIR/ctd/${CAST_NAME}.${ext}"
done
rm -rf "$TMP"

echo "fetch_cast_ctd: $CAST_NAME -> $STAGING_DIR/ctd/"
SCRIPT_EOF
chmod +x nuyina_data/scripts/fetch_cast_ctd.sh
```

- [ ] **Step 2: `nuyina_data/scripts/fetch_cast_nav.sh`**

```bash
cat > nuyina_data/scripts/fetch_cast_nav.sh <<'SCRIPT_EOF'
#!/usr/bin/env bash
# AAD/Nuyina-specific: derives a cast's real start time from its just-
# fetched .hdr file, rclone-pulls the matching day's GNGGA proc/csv
# extract, and runs the parameterized gngga_to_navtable.py to produce the
# plain-numeric nav table process_cast.sh needs. NOT part of the public
# repo -- see
# docs/superpowers/specs/2026-09-06-generic-cast-processing-script-design.md.
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: $0 <voyage> <cast>  (e.g. $0 202324050 004)" >&2
  exit 1
fi
VOYAGE="$1"
CAST="$2"
CAST_NAME="${VOYAGE}_${CAST}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LDEO_REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
NUYINA_ROOT="$(cd "$LDEO_REPO_ROOT/.." && pwd)"
ENV_FILE="$NUYINA_ROOT/.env"
STAGING_DIR="$LDEO_REPO_ROOT/nuyina_data/$CAST_NAME"
HDR_FILE="$STAGING_DIR/ctd/${CAST_NAME}.hdr"

if [ ! -f "$HDR_FILE" ]; then
  echo "fetch_cast_nav: $HDR_FILE not found -- run fetch_cast_ctd.sh first" >&2
  exit 1
fi

CAST_START_ISO=$("$LDEO_REPO_ROOT/.venv312/bin/python" - "$HDR_FILE" <<'PYEOF'
import re, sys
from datetime import datetime
text = open(sys.argv[1]).read()
match = re.search(r"System UpLoad Time = (\w+ \d+ \d+ \d+:\d+:\d+)", text)
if not match:
    raise SystemExit(f"no 'System UpLoad Time' line found in {sys.argv[1]}")
dt = datetime.strptime(match.group(1), "%b %d %Y %H:%M:%S")
print(dt.strftime("%Y-%m-%dT%H:%M:%SZ"))
PYEOF
)
echo "fetch_cast_nav: cast start = $CAST_START_ISO"
CAST_DATE="${CAST_START_ISO%%T*}"

for var in S3_HOST S3_ACCESS_KEY S3_SECRET_KEY S3_BUCKET; do
  value="$(grep -E "^${var}=" "$ENV_FILE" | tail -1 | cut -d= -f2-)"
  printf -v "$var" '%s' "$value"
done
export RCLONE_CONFIG_AADCKINGSTON_TYPE=s3
export RCLONE_CONFIG_AADCKINGSTON_PROVIDER=Other
export RCLONE_CONFIG_AADCKINGSTON_ENDPOINT="$S3_HOST"
export RCLONE_CONFIG_AADCKINGSTON_ACCESS_KEY_ID="$S3_ACCESS_KEY"
export RCLONE_CONFIG_AADCKINGSTON_SECRET_ACCESS_KEY="$S3_SECRET_KEY"

mkdir -p "$STAGING_DIR/nav"
CSV_PATH="$STAGING_DIR/nav/GNGGA_${CAST_DATE}.csv"
rclone copyto "aadckingston:$S3_BUCKET/$VOYAGE/dgps/proc/csv/GNGGA/GNGGA_${CAST_DATE}.csv" "$CSV_PATH"

"$LDEO_REPO_ROOT/.venv312/bin/python" "$LDEO_REPO_ROOT/scripts/gngga_to_navtable.py" \
  "$CSV_PATH" "$STAGING_DIR/nav/${CAST_NAME}.navtable" --cast-start "$CAST_START_ISO"

echo "$CAST_START_ISO" > "$STAGING_DIR/nav/.cast_start"
echo "fetch_cast_nav: $CAST_NAME -> $STAGING_DIR/nav/${CAST_NAME}.navtable"
SCRIPT_EOF
chmod +x nuyina_data/scripts/fetch_cast_nav.sh
```

- [ ] **Step 3: `nuyina_data/scripts/derive_ctd_cast_config.py`**

```bash
cat > nuyina_data/scripts/derive_ctd_cast_config.py <<'SCRIPT_EOF'
#!/usr/bin/env python3
"""AAD/Nuyina-specific: runs the same conversion the webapp's own
POST /api/quick-convert/ctd uses (ctdam.conv.decode_hex + CTDData.to_cnv),
purely to inspect the resulting .cnv's real column layout and cast
duration BEFORE scripts/process_cast.sh needs them in cast-config.json.
scripts/process_cast.sh re-runs the same deterministic conversion for
real inside the container -- running it twice is harmless.

NOT part of the public repo -- see
docs/superpowers/specs/2026-09-06-generic-cast-processing-script-design.md.

Usage: derive_ctd_cast_config.py <hex_path> <xmlcon_path> <cast_start_iso8601>
Prints a JSON object with ctd_* CastEntry fields plus time_start/time_end,
to be merged into the cast's cast-config.json.
"""
import json
import re
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

_NAME_LINE = re.compile(r"^#\s*name\s+(\d+)\s*=\s*([^:]+):")
_WANTED_SHORT_NAMES = ("timeS", "prDM", "t090C", "sal00")


def _is_number(token: str) -> bool:
    try:
        float(token)
        return True
    except ValueError:
        return False


def derive(hex_path: Path, xmlcon_path: Path, cast_start: datetime) -> dict:
    from ctdam.conv import decode_hex

    ctd_data = decode_hex(hex_path, xmlcon_path)
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "preview.cnv"
        ctd_data.to_cnv(str(out_path))
        lines = [
            line for line in out_path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip() != ""
        ]

    column_index = {}
    for line in lines:
        match = _NAME_LINE.match(line)
        if match:
            index, short_name = int(match.group(1)), match.group(2).strip()
            if short_name in _WANTED_SHORT_NAMES:
                column_index[short_name] = index

    missing = [name for name in _WANTED_SHORT_NAMES if name not in column_index]
    if missing:
        raise SystemExit(f"could not find expected column(s) {missing} in converted .cnv header")

    header_lines = 0
    for line in lines:
        tokens = line.strip().split()
        if tokens and all(_is_number(t) for t in tokens):
            break
        header_lines += 1
    data_lines = [line.split() for line in lines[header_lines:]]
    if not data_lines:
        raise SystemExit("no numeric data rows found in converted .cnv")

    fields_per_line = len(data_lines[0])
    last_elapsed_seconds = float(data_lines[-1][column_index["timeS"]])
    time_end = cast_start + timedelta(seconds=last_elapsed_seconds)

    return {
        "ctd_header_lines": header_lines,
        "ctd_fields_per_line": fields_per_line,
        # "# name N = ..." lines are 0-indexed; CastEntry's *_field values
        # are 1-indexed (Octave/MATLAB column numbers).
        "ctd_time_field": column_index["timeS"] + 1,
        "ctd_pressure_field": column_index["prDM"] + 1,
        "ctd_temperature_field": column_index["t090C"] + 1,
        "ctd_salinity_field": column_index["sal00"] + 1,
        "ctd_badvals": -9e99,
        "ctd_time_base": 0,
        "time_start": [
            cast_start.year, cast_start.month, cast_start.day,
            cast_start.hour, cast_start.minute, cast_start.second,
        ],
        "time_end": [
            time_end.year, time_end.month, time_end.day,
            time_end.hour, time_end.minute,
            time_end.second + time_end.microsecond / 1e6,
        ],
    }


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"usage: {sys.argv[0]} <hex_path> <xmlcon_path> <cast_start_iso8601>", file=sys.stderr)
        raise SystemExit(1)
    cast_start = datetime.fromisoformat(sys.argv[3].replace("Z", "+00:00"))
    print(json.dumps(derive(Path(sys.argv[1]), Path(sys.argv[2]), cast_start)))
SCRIPT_EOF
chmod +x nuyina_data/scripts/derive_ctd_cast_config.py
```

- [ ] **Step 4: Verify `derive_ctd_cast_config.py` against cast 005's already-known-good values**

Since this script isn't committed, its correctness is verified directly against real ground
truth already established this session, rather than a checked-in pytest file:

```bash
.venv312/bin/python nuyina_data/scripts/derive_ctd_cast_config.py \
  nuyina_data/202324050_005/ctd/202324050_005.hex \
  nuyina_data/202324050_005/ctd/202324050_005.XMLCON \
  2024-06-17T03:43:15Z
```

Expected (matching the real, already-verified `202324050_005.UNVALIDATED_QUICKCONVERT.cnv`):
`ctd_header_lines: 283`, `ctd_fields_per_line: 19`, `ctd_time_field: 11`,
`ctd_pressure_field: 2`, `ctd_temperature_field: 3`, `ctd_salinity_field: 5`,
`time_start: [2024,6,17,3,43,15]`, `time_end: [2024,6,17,4,24,28.917]` (the last CTD scan's
`timeS` value, 2473.917 seconds, added to the cast start — confirmed this session against the
real file: `tail -1 nuyina_data/202324050_005/data/quick_convert/202324050_005.UNVALIDATED_QUICKCONVERT.cnv`'s
11th column is `2473.917`). A mismatch means a bug in this script — fix it before Step 5.

- [ ] **Step 5: `nuyina_data/scripts/process_nuyina_cast.sh`**

```bash
cat > nuyina_data/scripts/process_nuyina_cast.sh <<'SCRIPT_EOF'
#!/usr/bin/env bash
# AAD/Nuyina-specific: fetches one real cast's CTD + nav inputs from the
# aadc-kingston shore bucket, reuses this voyage's already-local LADCP raw
# files and already-produced SADCP CODAS output, derives the CTD column
# mapping and cast duration, builds a cast-config.json, and hands off to
# the generic scripts/process_cast.sh. NOT part of the public repo -- see
# docs/superpowers/specs/2026-09-06-generic-cast-processing-script-design.md.
#
# Usage: process_nuyina_cast.sh <voyage> <cast>  (e.g. 202324050 004)
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: $0 <voyage> <cast>  (e.g. $0 202324050 004)" >&2
  exit 1
fi
VOYAGE="$1"
CAST="$2"
CAST_NAME="${VOYAGE}_${CAST}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LDEO_REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
NUYINA_ROOT="$(cd "$LDEO_REPO_ROOT/.." && pwd)"
STAGING_DIR="$LDEO_REPO_ROOT/nuyina_data/$CAST_NAME"

mkdir -p "$STAGING_DIR"/ctd "$STAGING_DIR"/nav "$STAGING_DIR"/codas "$STAGING_DIR"/data

echo "=== fetching CTD ==="
"$SCRIPT_DIR/fetch_cast_ctd.sh" "$VOYAGE" "$CAST"

echo "=== fetching nav ==="
"$SCRIPT_DIR/fetch_cast_nav.sh" "$VOYAGE" "$CAST"
CAST_START_ISO="$(cat "$STAGING_DIR/nav/.cast_start")"

echo "=== staging LADCP raw files ==="
LADCP_SRC="$NUYINA_ROOT/nuyina_dev_env/voyage_data/sample/adcp/ladcp"
SHORT_VOYAGE="${VOYAGE#20}"
LADCPDO="${SHORT_VOYAGE}_${CAST}_down_ladcp.000"
LADCPUP="${SHORT_VOYAGE}_${CAST}_up_ladcp.000"
if [ ! -f "$LADCP_SRC/$LADCPDO" ] || [ ! -f "$LADCP_SRC/$LADCPUP" ]; then
  echo "error: LADCP raw files not found for cast $CAST at $LADCP_SRC" >&2
  exit 1
fi
cp "$LADCP_SRC/$LADCPDO" "$LADCP_SRC/$LADCPUP" "$STAGING_DIR/ladcp/"

echo "=== staging SADCP CODAS contour ==="
CODAS_SRC="$NUYINA_ROOT/nuyina_uhdas_codas/output/nuyina_${VOYAGE}/os150nb/contour"
if [ ! -f "$CODAS_SRC/contour_xy.mat" ] || [ ! -f "$CODAS_SRC/contour_uv.mat" ]; then
  echo "error: SADCP contour not found at $CODAS_SRC" >&2
  exit 1
fi
rm -rf "$STAGING_DIR/codas/contour"
mkdir -p "$STAGING_DIR/codas/contour"
cp "$CODAS_SRC"/contour_xy.mat "$CODAS_SRC"/contour_uv.mat "$STAGING_DIR/codas/contour/"

echo "=== deriving CTD column mapping and cast duration ==="
CTD_FRAGMENT=$("$LDEO_REPO_ROOT/.venv312/bin/python" "$SCRIPT_DIR/derive_ctd_cast_config.py" \
  "$STAGING_DIR/ctd/${CAST_NAME}.hex" "$STAGING_DIR/ctd/${CAST_NAME}.XMLCON" "$CAST_START_ISO")

echo "=== deriving cast-start position from nav table ==="
read -r NAV_LAT NAV_LON < <(awk '
  NR == 1 { mind = ($1 < 0 ? -$1 : $1); lat = $2; lon = $3 }
  NR > 1  { d = ($1 < 0 ? -$1 : $1); if (d < mind) { mind = d; lat = $2; lon = $3 } }
  END { print lat, lon }
' "$STAGING_DIR/nav/${CAST_NAME}.navtable")

echo "=== writing cast-config.json ==="
jq -n \
  --arg cast_name "$CAST_NAME" \
  --argjson station "$CAST" \
  --arg ladcpdo "$LADCPDO" \
  --arg ladcpup "$LADCPUP" \
  --arg ctd_hex "${CAST_NAME}.hex" \
  --arg ctd_xmlcon "${CAST_NAME}.XMLCON" \
  --arg nav "${CAST_NAME}.navtable" \
  --argjson lat "$NAV_LAT" \
  --argjson lon "$NAV_LON" \
  --argjson ctd_fragment "$CTD_FRAGMENT" \
  '{
    station: $station,
    cast_name: $cast_name,
    ladcpdo: $ladcpdo,
    ladcpup: $ladcpup,
    ctd_hex: $ctd_hex,
    ctd_xmlcon: $ctd_xmlcon,
    nav: $nav,
    nav_header_lines: 0,
    nav_fields_per_line: 3,
    nav_time_field: 1,
    nav_lat_field: 2,
    nav_lon_field: 3,
    sadcp_contour_dir: "contour",
    lat: $lat,
    lon: $lon
  } + $ctd_fragment' > "$STAGING_DIR/cast-config.json"

echo "=== running scripts/process_cast.sh ==="
"$LDEO_REPO_ROOT/scripts/process_cast.sh" "$STAGING_DIR" "$STAGING_DIR/cast-config.json"
SCRIPT_EOF
chmod +x nuyina_data/scripts/process_nuyina_cast.sh
```

- [ ] **Step 6: Confirm nothing from this task is tracked by git**

```bash
git status --short nuyina_data/
```

Expected: empty output (the whole `nuyina_data/` directory is gitignored, so nothing here shows
up as untracked or staged). If anything appears, stop — do not commit it; investigate why
`.gitignore`'s `nuyina_data/` rule didn't cover it.

No commit for this task by design — these four files must never enter git history.

---

### Task 6: Real end-to-end run — cast 004

**Files:** none (this task only runs the tools built above against real data)

**Interfaces:**
- Consumes: `nuyina_data/scripts/process_nuyina_cast.sh` from Task 5.
- Produces: nothing consumed by later tasks — independent verification of a second real cast.

- [ ] **Step 1: Run it**

```bash
nuyina_data/scripts/process_nuyina_cast.sh 202324050 004
```

Expected: exits 0, prints the real fetch/derive/generate/process_cast output through to
completion.

- [ ] **Step 2: Inspect the real output**

```bash
docker run --rm -v "$(pwd)/nuyina_data/202324050_004/data:/data" ldeo-ix-octave \
  octave-cli --eval "load /data/V7/202324050_004.mat; disp(dr.u([1 end])); disp(dr.v([1 end])); disp(p.drot)"
```

(Adjust the variable names if `whos -file /data/V7/202324050_004.mat` shows a different
structure than cast 005's, same caveat as Task 4 Step 4.)

Expected: a genuine, non-empty, non-NaN `u`/`v` velocity profile and a real (non-placeholder)
`drot` value computed by `process_cast`'s own step 3 — not copied from cast 005, since this is a
different cast with different real nav data. If the run produced NaN or empty output, that's a
real finding — investigate the real cause (most likely a bad column-mapping assumption in
`derive_ctd_cast_config.py`, or the LADCP scan-time window not actually covering the real cast
duration) rather than reporting success anyway.

- [ ] **Step 3: Record the real captured output**

The task report must quote the actual terminal output of Steps 1 and 2 verbatim, with real
numbers — never a template or a copy of cast 005's/006's numbers.

No commit for this task.

---

### Task 7: Real end-to-end run — cast 006

**Files:** none (mirrors Task 6 for the third and final cast of this voyage)

**Interfaces:**
- Consumes: `nuyina_data/scripts/process_nuyina_cast.sh` from Task 5.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Run it**

```bash
nuyina_data/scripts/process_nuyina_cast.sh 202324050 006
```

Expected: exits 0, prints the real fetch/derive/generate/process_cast output through to
completion.

- [ ] **Step 2: Inspect the real output**

```bash
docker run --rm -v "$(pwd)/nuyina_data/202324050_006/data:/data" ldeo-ix-octave \
  octave-cli --eval "load /data/V7/202324050_006.mat; disp(dr.u([1 end])); disp(dr.v([1 end])); disp(p.drot)"
```

Expected: a genuine, non-empty, non-NaN `u`/`v` velocity profile and a real `drot` value
distinct from casts 004 and 005 (different cast, different real position/time, different
declination).

- [ ] **Step 3: Record the real captured output**

Same requirement as Task 6 Step 3 — real, verbatim output, not a template.

- [ ] **Step 4: Final confirmation that no uncommitted-tooling constraint was violated**

```bash
git status --short
```

Expected: clean (or only showing files unrelated to this plan) — `nuyina_data/` contributes
nothing, since it's gitignored in full. This is the plan's final gate per the Global Constraints
section above.

No commit for this task.
