# Real Nuyina LADCP Cast Processing — Design

Status: Draft

## Context

`nuyina_uhdas_codas` (sister repo, Bitbucket) just shipped a script that fetches RSV *Nuyina*
voyage 202324050's real vessel-mounted ADCP (VM-ADCP / SADCP) data from the AAD shore-side S3
bucket and runs it through UHDAS+CODAS, producing `contour/{contour_xy.mat,contour_uv.mat}` for
both OS150 and OS38 instruments. Its design spec explicitly deferred "wire the two repos' outputs
together for a real end-to-end VM-ADCP + LADCP voyage" until this repo's own SADCP-conversion
feature landed. It has now landed (`5d31b62` and follow-ups, on `master`): the webapp's **Convert
CODAS SADCP data** feature reads a CODAS instrument's `contour/` directory and produces the `.mat`
file `loadsadcp.m` expects — a direct port of `ldeo_ix/mkSADCP.m`.

The same voyage has real LADCP raw casts already sitting locally in `nuyina_dev_env` (added during
`nuyina_uhdas_codas`'s Phase 2): three casts, 004/005/006, each a down-looking and up-looking RDI
PD0 binary pair. The AAD shore-side S3 bucket additionally has, for the same voyage: raw Sea-Bird
CTD data per cast (`.hex`+`.XMLCON`+`.hdr`+`.bl` under `202324050/ctd/ctd_seabird/raw/seasave/`,
casts 001 through 010 — no pre-converted `.cnv` exists) and raw Kongsberg navigation text, one file
per day, under `202324050/{dgps,gps_compass}/raw/`.

**Goal:** process one real LADCP cast (005) all the way through `process_cast()`'s real 17 steps,
producing genuine LADCP velocity output, using this voyage's real CTD, real navigation, and the
real SADCP reference `nuyina_uhdas_codas` already produced — not a worked example with placeholder
inputs.

## Scope

- One cast: 005. The other two (004, 006) are the same recipe repeated once this proves out — not
  built here.
- CTD: cast 005's raw `.hex`+`.XMLCON` pair, converted via the webapp's existing **Quick-convert
  raw hex** feature (`POST /api/quick-convert/ctd`) — the only option available, since no
  pre-converted `.cnv` exists for this voyage. Its `UNVALIDATED_QUICKCONVERT` naming and caveat are
  accepted as-is; this is a real, known limitation of Quick-convert's science quality, not
  something this task fixes.
- Navigation: the raw Kongsberg daily text file(s) covering cast 005's actual cast time, mapped via
  the webapp's existing generic Time/Lat/Lon column-mapping (same mechanism as CTD's preview/map
  flow) — no new parsing code.
- SADCP: `nuyina_uhdas_codas`'s already-produced `output/nuyina_202324050/os150nb/contour/`,
  converted via the webapp's existing `POST /api/sadcp/convert`. **OS150, not OS38** — the
  shallower, higher-frequency instrument is the conventional SADCP reference for LADCP processing
  (better near-surface resolution, which is what LADCP's shear-based inverse solution leans on).
  If the resulting solution looks poor, OS38 is the fallback to try, but this isn't expected to be
  needed for a first real pass.
- LADCP raw data: `nuyina_dev_env/voyage_data/sample/adcp/sadcp/../ladcp/` (already local, from
  Phase 2) — no S3 fetch needed for this.
- Driving mechanism: the webapp's FastAPI endpoints called directly (`curl`/a short script), not
  browser interaction. No new endpoints — every step below already exists in the shipped webapp.
- Verification: an actual `process_cast(5, 1, 0)` run inside the Octave container (all 17 real
  steps), followed by inspecting the real saved output for a genuine, non-empty velocity profile —
  not just confirming `set_cast_params.m` is well-formed. (Corrected from an earlier draft's
  `process_cast(5,1,2)`: `stop=2` never resets and pauses after every single step forever, which
  hangs a non-interactive run — discovered the hard way during this plan's own execution; see
  `.superpowers/sdd/2026-09-06-nuyina-ladcp-cast-processing/task-3-report.md`.)

**Non-goals:** processing casts 004/006 in this pass; building any new S3-fetch script for this
repo (CTD/nav are one-off `rclone` pulls into a local staging directory, not a persisted tool —
LADCP needs no fetch at all, it's already local); any change to `nuyina_uhdas_codas` itself; any
change to Quick-convert's or SADCP-convert's actual conversion logic; a new Moodle course (still
future work per the sister spec).

## Data Flow

```
S3 (aadc-kingston)              nuyina_dev_env (local)         nuyina_uhdas_codas (local)
  ctd/.../202324050_005.*  ─┐    voyage_data/.../ladcp/  ─┐    output/nuyina_202324050/
  {dgps,gps_compass}/raw/* ─┤    (cast 005 down+up)       │      os150nb/contour/
  (one-off rclone pull)     │                             │      {contour_xy,contour_uv}.mat
                            ▼                             ▼        │
                   local staging dir ("nuyina_data/")  ───┴────────┘
                            │
                            ▼
              LDEO_IX_Octave webapp, 5 mounts:
              /data (rw), /ladcp_data, /ctd_data,
              /navigation_data, /codas_data (all ro
              except /data)
                            │
       ┌────────────────────┼─────────────────────┐
       ▼                    ▼                      ▼
  POST /api/quick-    POST /api/sadcp/       GET /api/ladcp/scan
  convert/ctd         convert                (confirm cast 005
  → data/quick_       → data/sadcp_convert/    down/up pair found)
  convert/*.cnw         os150nb.SADCP.mat
       │                    │                      │
       └────────────────────┴──────────────────────┘
                            ▼
        POST /api/session/casts (cast 5, pointing at all
        four real inputs above) → PUT nav column mapping
        → POST /api/generate → /data/set_cast_params.m
                            ▼
        docker run ... octave-cli --eval "process_cast(5,1,0)"
        (real 17-step pipeline, inside the same container)
                            ▼
        Inspect real saved output (per set_cast_params.m's
        f.res path) for a genuine, non-empty velocity profile
```

## Staging Directory and Mounts

A local directory (e.g. `nuyina_data/202324050_005/` inside this repo, gitignored — it holds
voyage data, not code) collects everything the webapp needs to read, laid out to match its mount
expectations:

- `ctd/` — cast 005's fetched `.hex`/`.XMLCON`/`.hdr`/`.bl` → mounted at `/ctd_data`
- `nav/` — the fetched daily Kongsberg text file(s) covering cast 005 → mounted at `/navigation_data`
- `codas/` — a copy of (or bind-mount straight to) `nuyina_uhdas_codas/output/nuyina_202324050/os150nb/`
  → mounted at `/codas_data`
- `data/` — empty to start, becomes the working directory (`quick_convert/`, `sadcp_convert/`,
  and eventually `set_cast_params.m` and real output all land here) → mounted at `/data`, must be
  writable
- LADCP: mount `nuyina_dev_env/voyage_data/sample/adcp/ladcp/` directly at `/ladcp_data` — no
  copying needed, it's already the right shape.

## Determining Cast 005's Actual Time (needed to pick the right nav file)

The raw Sea-Bird `.hdr` file for cast 005 (`202324050_005.hdr`) contains a real start-time
timestamp in its header text — read that first, before fetching navigation data, to know which
day's `dgps`/`gps_compass` file(s) actually cover the cast (a cast near a day boundary may need
two consecutive days' files). Don't guess the date from the voyage's overall June 2024 date range.

## Verification

1. Fetch cast 005's CTD raw pair and the correct day's nav file(s) from S3 into the staging
   directory (Context section's rationale: no persisted script, this is a one-off `rclone copyto`
   per file).
2. Start the webapp container with all five mounts from the section above.
3. `GET /api/mounts` — confirm all five report available.
4. `GET /api/ladcp/scan` — confirm cast 005's down/up pair is detected with the expected filenames.
5. `POST /api/quick-convert/ctd` with cast 005's hex/XMLCON paths — confirm a 200 response and a
   real `*.UNVALIDATED_QUICKCONVERT.cnv` file appears under `data/quick_convert/`.
6. `POST /api/sadcp/convert` with the OS150 `contour/` path — confirm a 200 response and a real
   `os150nb.SADCP.mat` (or equivalent name) appears under `data/sadcp_convert/`.
7. Create the cast session (`POST /api/session/casts`), set nav column mapping, point every field
   at the real files from steps 4-6, then `POST /api/generate` — confirm `/data/set_cast_params.m`
   is written and, read back, actually references the real file paths (not empty/placeholder
   fields).
8. `docker run --rm -v <staging>/data:/data ldeo-ix-octave octave-cli --eval "process_cast(5,1,0)"`
   — confirm it runs to completion without an Octave error, through all 17 steps.
9. Inspect the real saved output (the file `set_cast_params.m`'s `f.res` field points at) — confirm
   it contains an actual, non-empty velocity profile (real u/v values across a real depth range),
   not an empty or all-NaN result.

## Future work (explicitly out of scope here)

- Casts 004 and 006, once this recipe is proven.
- A reusable S3-fetch script for this repo, if a second voyage or a batch workflow is ever wanted.
- A combined VM-ADCP + LADCP training module (Moodle), per the sister spec's own deferred item.
