# Cruise/Cast Intake Form — Design

Date: 2026-07-15
Status: Approved for planning

## Context

`ldeo-ix-octave` currently packages LDEO_IX to run under Octave inside a
Docker image with no web interface at all — it's a thin CLI wrapper. The
longer-term goal (confirmed with the user, out of scope for this doc) is a
web interface bundled into the image that covers four areas:

1. Cruise/cast intake — generating `set_cast_params.m` (**this slice**)
2. A documentation browser (PDFs/docs from the sister `Nuyina/LADCP` project)
3. An output viewer (browsing/displaying results after `process_cast` runs)
4. A global-variable/defaults editor (cruise-wide `p`/`f`/`ps`/`att` fields)
5. Eventually, full run orchestration — the web UI invoking `process_cast`
   itself, with live progress and checkpoint resume through the UI

These are being built incrementally, each as its own spec → plan → build
cycle. This document covers **only** the cruise/cast intake form (item 1),
which also stands up the web server skeleton the later slices will build on.

This tool is for cruise/cast metadata **only** (LADCP casts during a
research cruise) — it is explicitly not being designed to generalize to
long-term mooring data processing; that was considered and ruled out during
design.

## Goal

Replace hand-editing `set_cast_params.m` with a web form that generates it
for a whole cruise (multiple casts, one `switch(stn) ... case` file),
inferring as many of the ~30 fields as possible from the actual CTD/raw/nav
data files rather than requiring manual entry, with a human-in-the-loop step
wherever a field can't be inferred unambiguously.

## Explicitly out of scope for this slice

- Documentation browser, output viewer, global-variable/defaults editor, run
  orchestration — future slices.
- Parsing an existing hand-written `set_cast_params.m` back into the form.
  The tool is write-only: it generates a fresh file each time from the
  in-session cast list, backing up whatever was there before. Round-tripping
  arbitrary hand-written M-code is a much harder problem (a real parser, not
  a template generator) and isn't needed for the first slice to be useful.
- Any change to `ldeo_ix/` itself. This slice is purely additive — no
  `CHANGES.md` entry needed.

## Architecture

**Stack:** Python backend (FastAPI) + server-rendered Jinja2 templates +
vanilla JS for the interactive bits (file browsing, column-mapping clicks).
No Node/build toolchain. This keeps the image lean and matches the tool's
actual size — a small internal scientific instrument, not a product with a
frontend team behind it. Python is added to the Dockerfile alongside Octave.

**Container entrypoint:** `docker run ldeo-ix-octave` starts the FastAPI
server (default port, e.g. 8080) instead of dropping straight into
`octave-cli`. The original CLI workflow remains available via
`docker run ldeo-ix-octave octave-cli` or `docker exec` into a running
container — this is a behavior change from today's default and must be
called out in `README.md`.

**Mounts** — all optional except `/data`; the backend only offers browsing
for whichever mounts are actually present at container start:

| Mount | Purpose |
|---|---|
| `/data` | Working directory — generated `set_cast_params.m`, session sidecar JSON, checkpoints, output `.nc` (existing convention, unchanged) |
| `/ladcp_data` | Raw RDI down/up cast files |
| `/ctd_data` | CTD time-series files |
| `/sadcp_data` | Shipboard ADCP `.mat` files |
| `/navigation_data` | Nav time-series files |

Each mount is a hard root boundary for the file browser: every browse/read
operation resolves the requested path and asserts it stays under its
declared mount root before touching disk. This is a **hard requirement**,
not a nice-to-have — the browser-facing file picker is the main new attack
surface this slice introduces, and a path like `../../etc/passwd` or a
symlink escaping the mount root must be rejected.

## Data model

**Cruise session** — an ordered list of **cast entries**, held in backend
memory and auto-saved to `/data/.cruise_intake_session.json` after every
add/edit. Opening the tool loads this sidecar if it exists, so a browser
refresh or container restart doesn't lose in-progress work. This JSON is
intake-tool state only; `process_cast.m`/LDEO_IX never reads it, and it's
independent of the generated `set_cast_params.m`.

**Cast entry** — mirrors the fields in
`examples/set_cast_params_P16N_example.m`:

- Raw data: `f.ladcpdo`, `f.ladcpup`, `p.ladcp_station`, `p.ladcp_cast`, `p.name`
- CTD: `f.ctd`, `f.ctd_header_lines`, `f.ctd_fields_per_line`,
  `f.ctd_time_field`, `f.ctd_pressure_field`, `f.ctd_temperature_field`,
  `f.ctd_salinity_field`, `f.ctd_badvals`, `f.ctd_time_base`
- Nav: `f.nav`, `f.nav_header_lines`, `f.nav_fields_per_line`,
  `f.nav_time_field`, `f.nav_lat_field`, `f.nav_lon_field`,
  `f.nav_time_base`, `p.nav_time_base`, `p.nav_error`
- SADCP: `f.sadcp` (optional — omitted cleanly if unset, matching
  `loadsadcp.m`'s existing `existf` check)
- Position/time: `p.drot`, `p.lat`, `p.lon`, `p.time_start`, `p.time_end`
- Bottom tracking: `p.btrk_mode`, `p.btrk_used`
- Output/checkpoints: `f.checkpoints`, `f.res`, `p.checkpoints`

## Workflow

### Adding a cast — three starting points

1. **From scratch** — blank entry.
2. **Clone from another cast in this session** — copies all fields; the
   user then changes whatever's cast-specific (station/cast/name at
   minimum). Most fields (field-mapping indices, `drot`, `btrk_mode`) are
   genuinely constant across a cruise, so this is the expected common path
   after the first cast.
3. **Clone from a prior output `.nc`** — reads the flattened `p`-struct
   attributes off a previously-processed cast's output netCDF and pre-fills
   from that. Useful when starting a new cruise's intake informed by a
   previous cruise's processed results, or recovering field values for a
   cast whose original `set_cast_params.m` was lost.

### Per-cast fill-in

- **Raw LADCP files** — backend scans `/ladcp_data`, groups files by
  leading station number, guesses down vs. up by filename convention
  (`DL`/`UL`), pre-fills `f.ladcpdo`/`f.ladcpup`/`p.ladcp_station`/
  `p.ladcp_cast`/`p.name`. Presented as a picker for the user to confirm or
  correct — never silently trusted.
- **CTD/nav files** — user browses `/ctd_data` / `/navigation_data` and
  picks a file. Backend auto-detects `header_lines` (leading non-numeric
  lines) and `fields_per_line` (column count of the first data row)
  automatically. It then shows a preview table of the first ~10 parsed data
  rows; the user clicks a column header and assigns its role from a
  dropdown (Time / Pressure / Temperature / Salinity / Lat / Lon — CTD needs
  Time/Pressure/Temp/Salinity, nav needs Time/Lat/Lon). Selections map
  directly onto the corresponding `*_field` values. Columns can be left
  unassigned if not needed. `ctd_badvals` has no reliable structural
  signal and stays a manual field, defaulted to LDEO_IX's own built-in
  default (`-9e99`, per `loadctd.m`'s `setdefv` call) unless overridden.
- **SADCP file** — optional picker into `/sadcp_data`.
- **Position/time/bottom-tracking** — manual entry (`p.lat`, `p.lon`,
  `p.drot`, `p.time_start`, `p.time_end`, `p.btrk_mode`, `p.btrk_used`);
  nothing upstream reliably provides these. Pre-filled by whichever clone
  source (session cast or prior `.nc`) was used to start the entry.
- **Checkpoints/output paths** — derived automatically from the cast
  name/number following the existing convention (`checkpoints/<name>`,
  `V7/<name>`), overridable.

### Review and generation

- A table of all casts in the session, key fields visible, with per-row
  edit/remove, shown before generation.
- **Validation before generation:** required fields (raw file paths,
  station/cast numbers, `p.lat`/`p.lon`, `p.time_start`/`p.time_end`) must
  be present for every cast — generation is blocked with a per-cast,
  per-field error list if not. Referenced files are checked for existence
  and shown as warnings (not hard blocks — a file may legitimately not be
  mounted yet at intake time).
- **Generation** renders one `switch(stn) ... case N ... end` block from all
  casts in the session, matching the field layout/style of
  `examples/set_cast_params_P16N_example.m`. If `/data/set_cast_params.m`
  already exists, it's backed up first (`set_cast_params.m.bak.<timestamp>`)
  rather than overwritten silently. The tool can be re-run repeatedly —
  regeneration is idempotent given the same session state.

### Error handling

Malformed/unreadable CTD or nav files during preview parsing show an inline
error at the file-picker step rather than failing the whole session; that
field can be left unset on the cast and revisited later.

## NetCDF reading

Output `.nc` files are read via `scipy.io.netcdf_file` on the assumption
they're classic-format NetCDF3 (consistent with the existing LDEO_IX
pipeline's own netCDF writing). **This assumption must be confirmed against
a real output file during planning/implementation** (e.g. via `ncdump -h`)
before committing to that library — if the format turns out to be NetCDF4/
HDF5-based, a different reader (`netCDF4`, `h5netcdf`) is needed instead.

## Testing / verification

This slice adds the first real testable surface to the repo (previously:
no test suite, verify by building and running).

- **Backend unit tests** for logic that's easy to get subtly wrong:
  - CTD/nav structural sniffing (`header_lines`/`fields_per_line` detection)
  - LADCP down/up filename pairing and station/cast number extraction
  - The `set_cast_params.m` template generator (cast list → valid Octave)
  - Mount-root path-traversal guarding (`../` escapes, symlink escapes)
- **Manual end-to-end verification**, following this repo's existing
  pattern: `docker build`, run the container with the example cast's data
  mounted across the new named mounts, drive the intake flow through a
  browser, generate `set_cast_params.m`, and diff the result against
  `examples/set_cast_params_P16N_example.m`. Successfully reproducing that
  file's fields from the same underlying data is the acceptance bar for the
  inference logic.

## Documentation follow-up

`README.md` needs updating for: the new default entrypoint (web server
instead of `octave-cli`), the new named mounts, and how to reach the old
CLI workflow. `CLAUDE.md`'s repo layout table should gain an entry for the
new backend code once its directory structure exists.
