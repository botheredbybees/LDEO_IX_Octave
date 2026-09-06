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
table, one row per fix, no header. Columns are, in order: `elapsed_seconds`, `latitude_decimal_degrees`,
`longitude_decimal_degrees`:

```
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

## Pre-flight validation — the script fails fast with clear errors

Before starting any Docker container or processing step, `scripts/process_cast.sh` validates your
`cast-config.json` and staging directory against the contract described above, with explicit error
messages for any problems:

- **Required fields**: `station`, `cast_name`, `ladcpdo`, `ladcpup`, `nav`, `lat`, `lon`,
  `time_start`, `time_end` must all be present.
- **CTD source**: must provide either (`ctd_hex` AND `ctd_xmlcon` together) or `ctd_cnv` alone —
  not a mix, and not all three.
- **SADCP source**: can provide either `sadcp_contour_dir` or `sadcp_mat_path`, but not both.
  If you set `sadcp_contour_dir`, the staging directory must have a `codas/` subdirectory. If you
  set `sadcp_mat_path`, the staging directory must have a `sadcp/` subdirectory.
- **Magnetic declination**: the config must not include a `drot` field.

If any of these conditions fail, the script exits immediately with a clear error message — you
won't get a halfway-through-Docker error buried in logs. This means your fetch/prep script can
validate once and trust that if `process_cast.sh` runs, the inputs are good.

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
