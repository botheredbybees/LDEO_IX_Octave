# Generic Cast-Processing Script and Vessel Data Preparation Guide — Design

Status: Draft

## Context

The real Nuyina cast-005 processing run (`2026-09-06-nuyina-ladcp-cast-processing.md`) proved the
whole pipeline end-to-end — webapp API calls driving Quick-convert, SADCP-convert, cast-session
creation, and `/api/generate`, followed by a real `process_cast(5,1,0)` run — but every step was
done as one-off `curl` commands during that task's own dispatch. The user's next request ("run the
other casts from this voyage and probably at least one other before we jump into publication or
the Moodle course") means repeating that recipe for casts 004 and 006.

The first draft of this design combined two things in one script: driving the webapp+`process_cast`
pipeline (genuinely reusable by any vessel/organization), and fetching AAD's own CTD/nav data from
the shore S3 bucket (100% AAD-specific — bucket name, credentials, folder layout). Combining them
would have quietly turned a public, general-purpose repo into one that only really works for AAD,
contradicting this repo's own existing stance (the cast-005 spec's own Non-Goals: "building any new
S3-fetch script for this repo"). The user confirmed splitting them: a generic, committed tool plus
documentation for other organizations, and separate AAD-specific glue that stays out of git
entirely.

## Goal

1. A generic, vessel-agnostic script in this repo that drives the webapp API + `process_cast` for
   one cast, given local file paths already staged in the expected layout — no AWS/S3 code, no
   AAD-specific assumptions anywhere in it.
2. Documentation in this repo explaining the input contract each staged file must satisfy, so any
   organization can write their own fetch/prep script against it.
3. The actual Nuyina-specific fetch scripts for casts 004 and 006 of voyage 202324050 — built, but
   explicitly **not committed** to this repo.

## What's Actually Vessel-Specific (and what isn't)

Re-reading the webapp's real code (`webapp/main.py`, `webapp/delimited_parser.py`,
`webapp/models.py`) settles a question the first draft got wrong: Quick-convert (raw Sea-Bird
hex+XMLCON → `.cnv`) and SADCP-convert (CODAS `contour/` → `.mat`) are **already generic** —
Sea-Bird hex and CODAS contour directories are standard formats, not AAD inventions, and both
conversions already live behind existing, documented `/api/*` routes. They belong in the generic
tool, not the vessel-specific bucket.

(There are actually six mounts, not five — re-checking `webapp/config.py` after the first pass of
this design found a `sadcp` mount, `/sadcp_data`, distinct from `codas`, `/codas_data`: `sadcp` is
for an organization that already has a converted SADCP `.mat` file and wants to skip SADCP-convert
entirely, while `codas` is SADCP-convert's raw-CODAS-contour input. Corrected throughout below.)

The one genuinely vessel-specific step is **navigation**. `delimited_parser.sniff_and_preview()`
only recognizes whitespace-delimited, all-numeric data rows (`line.strip().split()` with no
delimiter argument) — it cannot read comma-separated CSV, NMEA sentences, or any text file with
non-numeric fields. Every organization's raw GPS/nav logging format differs, so producing a plain
numeric nav table is unavoidably a per-vessel prep step. `scripts/gngga_to_navtable.py` (already
committed from the cast-005 work) is AAD's own version of that step — it stays where it is rather
than being relocated for this design (already shipped, reviewed, low value in moving it now), but
its hardcoded `CAST_START` gets parameterized as part of this plan, since that was an explicit
forward-risk flagged by cast-005's own final review and casts 004/006 are exactly the situation it
warned about.

## Architecture

**Committed to this repo (generic):**

- `scripts/process_cast.sh <staging-dir> <cast-config.json> [image-tag]` — starts a container from
  the repo's one real image (default tag `ldeo-ix-octave`, overridable) in its default `serve` mode
  against a staging directory's mounts, drives Quick-convert/SADCP-convert (if the config asks for
  them), creates the cast session, calls `/api/generate`, stops that container, then runs
  `docker run ... ldeo-ix-octave octave-cli --eval "process_cast(<station>,1,0)"` against the same
  `/data` mount (the same `ENTRYPOINT`/`CMD` split the README's own two documented invocations
  already use — no new image, no new entrypoint mode). No vessel identity anywhere in the script;
  every fact about a specific cast comes from the config file and the staging directory.
- `docs/vessel-data-preparation.md` — the input contract (staging layout, the nav-table format
  requirement in detail, the two CTD input options, the optional SADCP input) and a walkthrough for
  writing your own fetch/prep script that ends by calling `process_cast.sh`.
- `scripts/gngga_to_navtable.py` gets a `--cast-start` CLI argument (ISO-8601), replacing the
  hardcoded cast-005 constant. Behaviour for cast 005 is unchanged when the new flag is passed
  cast 005's real start time; every other cast now has a real, working example of correct use
  rather than a footgun for the next cast.

**Not committed (AAD/Nuyina-specific, lives in the already-gitignored `nuyina_data/` directory):**

- `nuyina_data/scripts/fetch_cast_ctd.sh <voyage> <cast>` — `rclone` pull of a cast's raw
  `.hex`/`.XMLCON`/`.hdr`/`.bl` from the `aadc-kingston` bucket into
  `nuyina_data/<voyage>_<cast>/ctd/`.
- `nuyina_data/scripts/fetch_cast_nav.sh <voyage> <cast>` — reads the cast's real start time from
  the just-fetched `.hdr` file, `rclone`-pulls the correct day's (or two days', if the cast straddles
  midnight) Kongsberg GNGGA file(s), and runs the now-parameterized `gngga_to_navtable.py` to
  produce `nuyina_data/<voyage>_<cast>/nav/<voyage>_<cast>.navtable`.
- `nuyina_data/scripts/process_nuyina_cast.sh <voyage> <cast>` — thin wrapper: calls the two fetch
  scripts above, writes the cast's `cast-config.json` (reusing the SADCP contour and LADCP raw
  files already local from earlier work), then calls the generic `scripts/process_cast.sh`.

## `cast-config.json` Contract

A single JSON file mirrors the webapp's own `CastEntry` model (`webapp/models.py`) almost exactly,
so it's self-documenting against the real API rather than an invented format:

```json
{
  "station": 4,
  "cast_name": "202324050_004",
  "ladcpdo": "202324050_004.000",
  "ladcpup": "202324050_004up.000",
  "ctd_hex": "202324050_004.hex",
  "ctd_xmlcon": "202324050_004.XMLCON",
  "ctd_time_field": 0,
  "ctd_pressure_field": 1,
  "ctd_temperature_field": 2,
  "ctd_salinity_field": 3,
  "nav": "202324050_004.navtable",
  "nav_time_field": 0,
  "nav_lat_field": 1,
  "nav_lon_field": 2,
  "sadcp_contour_dir": "os150nb/contour",
  "lat": -63.512,
  "lon": 141.234,
  "time_start": [2024, 6, 17, 1, 10, 0],
  "time_end": [2024, 6, 17, 1, 55, 0]
}
```

- `ladcpdo`/`ladcpup` are paths relative to the `ladcp` mount; `ctd_hex`/`ctd_xmlcon` (or, if the
  organization already has a converted file, a single `ctd_cnv` path) relative to the `ctd` mount;
  `nav` relative to the `nav` mount.
- SADCP is optional and has two mutually exclusive forms, matching the two real mounts: either
  `sadcp_contour_dir` (relative to the `codas` mount — triggers `/api/sadcp/convert`, and the
  resulting output path becomes the cast body's `sadcp` field) or `sadcp_mat_path` (relative to the
  `sadcp` mount — an organization that already has a converted SADCP `.mat` skips SADCP-convert
  entirely, and this path is used directly as the cast body's `sadcp` field). Setting both is a
  config error the script rejects before starting any container.
- **`drot` is deliberately never set by this script or its config schema.** Per Andreas Thurnherr's
  own LDEO_IX manual (quoted in `HANDOVER.md` from this session's earlier research): once real GPS
  navigation is loaded, magnetic declination must be left to compute naturally in `process_cast`'s
  own step 3, not supplied manually — supplying it early changes a bottom-track QC threshold's
  timing and produces a materially different, non-equivalent solution. `docs/vessel-data-
  preparation.md` states this explicitly so nobody reintroduces the mistake this session already
  found and fixed.
- `time_start`/`time_end` use `process_cast`'s own six-element date-vector convention
  (`[Y, M, D, h, m, s]`), matching `CastEntry.time_start`/`time_end`'s existing shape — no new
  format invented.

## `process_cast.sh` Behaviour

1. Validate the staging directory has `ctd/`, `nav/`, `data/`, and `ladcp/` (and `codas/` if the
   config's `sadcp_contour_dir` is set, or `sadcp/` if it instead sets a pre-converted
   `sadcp_mat_path`); fail fast with a clear message naming the missing one.
2. `docker run -d -p <port>:8080 -v staging/data:/data -v staging/ladcp:/ladcp_data -v
   staging/ctd:/ctd_data -v staging/nav:/navigation_data [-v staging/codas:/codas_data] [-v
   staging/sadcp:/sadcp_data] <image-tag>` (CMD defaults to `serve`, matching the README's own web-
   form example exactly, mount-for-mount) — omit the `codas`/`sadcp` `-v` flags entirely when unused,
   per the existing README note that Docker would otherwise auto-create an empty directory and the
   webapp's SADCP UI section keys off the mount actually being present. Poll `/health` until it
   responds.
3. `GET /api/mounts` — confirm the mounts the config actually needs are present.
4. If `ctd_hex`/`ctd_xmlcon` are set (rather than `ctd_cnv`): `POST /api/quick-convert/ctd`,
   capture `ctd_path` from the response for the next step.
5. If `sadcp_contour_dir` is set: `POST /api/sadcp/convert`, capture `sadcp_path`.
6. `POST /api/session/casts` with the full cast body — `ctd` set to `ctd_path` from step 4 (or the
   config's own `ctd_cnv` if no quick-convert was needed); `sadcp` set to `sadcp_path` from step 5
   (or the config's own `sadcp_mat_path` if SADCP-convert wasn't needed, or omitted entirely if
   neither was given); everything else copied straight from the config; `drot` always omitted.
7. `POST /api/generate` — fail loudly on a non-2xx response (a validation error means the config is
   wrong, not that processing should proceed anyway).
8. Stop the container from step 2.
9. `docker run --rm -v <staging-dir>/data:/data <image-tag> octave-cli --eval
   "process_cast(<station>,1,0)"` — the real 17-step run. `stop=0` always, matching README's
   corrected guidance (`stop=2` never self-resets — see the cast-005 plan's own final review — so
   this script never exposes that footgun as an option).
10. Print the path to the real output (`data/<res_file>`) and the diary log for the caller to
    inspect.

## Documentation: `docs/vessel-data-preparation.md`

Written for an organization that has never seen this repo's internals. Covers:

- The staging layout (`ctd/`, `nav/`, `ladcp/`, `data/`, and the optional `codas/`/`sadcp/`) and
  what `process_cast.sh` expects to find in each.
- CTD: either a raw Sea-Bird `.hex`+`.XMLCON` pair (Quick-convert handles it, with the existing
  `UNVALIDATED_QUICKCONVERT` science-quality caveat carried over unchanged from the cast-005 work)
  or an already-converted `.cnv`/plain numeric file, if you already run real SBE Data Processing.
- **Navigation — the one step you'll need to build yourself.** Explains the plain
  whitespace-delimited, all-numeric contract `delimited_parser.py` requires, with a small worked
  example table, and points out that raw NMEA/CSV/proprietary logger exports must be converted to
  this shape first. Uses `gngga_to_navtable.py` as one illustrative example of what such a converter
  looks like (elapsed-seconds-since-cast-start, decimal-degree lat/lon), explicitly framed as "AAD's
  own converter for AAD's own logging format — yours will look different" rather than something to
  reuse verbatim.
- SADCP is optional; the CODAS `contour/` directory format is whatever `nuyina_uhdas_codas`
  (or any other UHDAS+CODAS pipeline) already produces — no new explanation needed beyond pointing
  at CODAS's own docs.
- The declination guidance from the "`drot`" bullet above, called out on its own so it isn't missed.
- A full worked `cast-config.json` example using placeholder vessel/cast names (not AAD's real
  identifiers, to keep the example genuinely vessel-neutral) and the exact `process_cast.sh`
  invocation that consumes it.
- A short "writing your own vessel-specific fetch script" section: fetch your raw data by whatever
  means your organization uses, convert nav to the contract above, stage everything into the
  staging directories, write a `cast-config.json`, call `process_cast.sh`. Notes that AAD's own such script
  exists but isn't part of this repo, for the reason given in Context.

## Verification

1. `webapp/tests` still pass unchanged (no route behaviour changes — `process_cast.sh` only calls
   existing endpoints).
2. A real dry run of `process_cast.sh` against the **existing cast-005 staging directory**
   (`nuyina_data/202324050_005/`), using a `cast-config.json` translated from that cast's already-
   known-good values — confirms the generic script reproduces the same real result HANDOVER.md
   already recorded (`u=[-0.071990, 0.166196]`, `v=[-0.087944, 0.265295]`, `drot=15.0572`) before
   trusting it on new casts. Any discrepancy is a bug in the new script, not a data problem, since
   the inputs are identical to the already-verified run.
3. `nuyina_data/scripts/process_nuyina_cast.sh 202324050 4` and
   `nuyina_data/scripts/process_nuyina_cast.sh 202324050 6` — two genuinely new real casts,
   end-to-end, each inspected for a real non-empty, non-NaN velocity profile the same way cast 005
   was.
4. A second voyage (202324060, already identified as having richer VM-ADCP coverage and 4 real
   LADCP casts) is explicitly **out of scope for this plan** — it needs its own SADCP processing
   pass through `nuyina_uhdas_codas` first (that repo's `entrypoint.sh` is still hardcoded to voyage
   202324050 and isn't part of this repo), and the user asked for "the other casts from this voyage
   **and probably at least one other**" — casts 004/006 satisfy "the other casts from this voyage";
   the second voyage is a follow-on, not bundled into this plan.

## Non-Goals

- Generalizing `nuyina_uhdas_codas`'s `entrypoint.sh` for arbitrary voyages — separate repo, own
  future plan, not touched here.
- Processing voyage 202324060 — follow-on work, needs its own VM-ADCP pass first.
- Any change to Quick-convert's or SADCP-convert's actual conversion logic — both already work,
  this design only calls them.
- A Moodle course or data-product/publication work — still deferred, per the user's own stated
  ordering.
- Making `gngga_to_navtable.py` itself vessel-agnostic (e.g. configurable column names) — it stays
  an AAD-specific converter that happens to live in this repo already; only its hardcoded cast-start
  timestamp is fixed here, per the concrete forward-risk that was actually flagged.
