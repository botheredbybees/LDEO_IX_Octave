# SADCP Extraction from CODAS Output

**Date:** 2026-09-06
**Status:** Approved for planning
**Source of truth:** `LDEO_IX_Octave/docs/superpowers/specs/2026-09-06-sadcp-codas-extract-design.md` (GitHub, `botheredbybees/LDEO_IX_Octave`) — this page is a published copy for team visibility, not the canonical edit location.

## Context

`ldeo_ix/loadsadcp.m` reads the cast's shipboard-ADCP (SADCP) reference field, `f.sadcp`, via a plain `load(f.sadcp)`. It expects a MATLAB/Octave `.mat` file already containing `tim_sadcp`, `lat_sadcp`, `lon_sadcp`, `u_sadcp(z,t)`, `v_sadcp(z,t)`, and `z_sadcp(z,1)` — i.e. an already-processed underway ADCP velocity time series, not a raw instrument file. Today the webapp's `sadcp` field is a plain browse/type-a-path input (`webapp/models.py`, `webapp/config.py`'s `sadcp` mount) with no logic behind it: the user is expected to already have a suitable `.mat` file from somewhere else.

The sister project `nuyina_uhdas_codas` runs the University of Hawaii's CODAS processing pipeline against RSV *Nuyina*'s shipboard ADCP and produces, per instrument (e.g. `os150nb`), a documented CODAS "short form" netCDF (`<instrument>.nc`) with exactly the fields needed here (`time`, `lon`, `lat`, `u`, `v`, `depth`) — already quality-edited and, per CODAS's own file documentation, "intended for most end-user scientific analysis and display purposes." No calibration is redone by this feature; it only reformats and slices an already-trustworthy product.

A separate idea raised during design — folding `LDEO_IX_Octave` and `nuyina_uhdas_codas` into a single project — was considered and rejected (by the user, immediately): the two have incompatible dependency footprints (a minimal Octave image vs. a heavy compiled toolchain), incompatible lifecycles (on-demand per-cast batch vs. a continuous 5-minute cron process against live ship data), and separate licensing-provenance stories (`NOTICE.md`'s careful `ldeo_ix`-only no-license disclosure vs. `pycurrents`/`codas3`/`onship`, whose licenses have not been reviewed). The two repos stay separate; this feature is the narrow interface between them — a documented file format, not shared code or infrastructure.

## Decision

Add a manual, per-cast, opt-in extraction step to the webapp: the user browses to a CODAS-produced `.nc` file (from wherever `nuyina_uhdas_codas`'s output is mounted) and the webapp slices out the time window around that cast, reformats it, and fills the existing `sadcp` field — mirroring the existing CTD "Quick-convert" flow's UX shape, but explicitly **not** named or labeled as a "quick and dirty" fallback, since no calibration is skipped here (unlike the CTD hex path, which does carry that disclaimer).

This entire feature is optional infrastructure: the `sadcp` field, and SADCP data generally, are already optional in LDEO_IX (`loadsadcp.m` only runs `if existf(f,'sadcp')==1`). The new UI only appears when a new `codas` mount is actually present, following the same `available_mounts()` pattern every other mount already uses — a cruise/machine with no `nuyina_uhdas_codas` data mounted sees nothing different from today.

Automatic, cruise-level extraction (point at a voyage's CODAS output root once, auto-slice every cast as it's added) was considered and explicitly deferred — it adds multi-instrument selection and auto-matching logic for a first version with no confirmed real-voyage usage yet. Manual per-cast, matching the existing file-picker pattern, is the smaller and more consistent starting point.

## Architecture

**New module:** `webapp/sadcp_extract.py`, pure-logic, parallel to `webapp/quick_convert.py`.

- Reads the CODAS `.nc` via `scipy.io.netcdf_file` — already a project dependency, already used the same way by `webapp/netcdf_reader.py` for reading a prior cast's output `.nc`. No new dependency.
- Validates the expected variables (`time`, `lon`, `lat`, `u`, `v`, `depth`) are present, to catch a user pointing at the wrong file (e.g. CODAS's "long form" dump instead of the short form).
- Converts the `time` variable ("days since `<yearbase>`-01-01", per the file's own `yearbase` global attribute) into the absolute Julian day number convention `ldeo_ix/julian.m` uses, via a small Python reimplementation of that same day-number formula. This is the one new piece of numeric logic in the feature and is directly unit-testable against known calendar dates.
- Selects ensembles whose converted time falls within `[cast.time_start − buffer, cast.time_end + buffer]`, where `cast.time_start`/`cast.time_end` are the Gregorian `[Y,M,D,H,M,S]` lists already stored on the cast (`webapp/models.py`'s `CastEntry.time_start`/`time_end`). Buffer defaults to **3 hours**, fixed (not a new persisted per-cast field, not user-configurable in this first version) — LADCP casts typically run 1–3 hours, and a few hours' padding gives `loadsadcp.m`'s own runtime windowing (`p.sadcp_dtok`) real data to work with without pulling in the whole voyage.
- Verifies the selected ensembles' `depth` rows are identical (CODAS bins are fixed per-instrument, but a mid-voyage reconfiguration is conceivable) and raises rather than silently picking one if they differ, collapsing to a single `z_sadcp` column vector.
- Transposes `u`/`v` from the netCDF's `(time, depth_cell)` layout into the `(depth, time)` layout `u_sadcp`/`v_sadcp` need, and converts the CODAS fill value (`1e38`) to `NaN`.
- Writes `tim_sadcp`, `lat_sadcp`, `lon_sadcp`, `u_sadcp`, `v_sadcp`, `z_sadcp` via `scipy.io.savemat` (MATLAB v5 format, which Octave's `load()` reads natively). No new dependency.

**New mount:** `config.py` gets a `"codas": Path(os.environ.get("LDEO_CODAS_DIR", "/codas_data"))` entry, following the existing mount-config pattern exactly. Like every other mount, it is only offered by `available_mounts()` (and therefore only shown in the UI) when the directory actually exists.

**New endpoint:** `POST /api/sadcp/extract` — body `{nc_path, time_start, time_end, buffer_hours}`, all resolved/validated the same way the existing `POST /api/quick-convert/ctd` endpoint resolves its inputs (`paths.resolve_within` against the `codas` mount). `time_start`/`time_end` come from the cast already open in the form (client-side state), so the endpoint stays stateless — no cast lookup or session access needed server-side, matching the CTD endpoint's shape. Deliberately **not** placed under `/api/quick-convert/`, to avoid implying this skips real processing the way the CTD hex fallback does.

Output is written to `{data_mount_root}/sadcp_extract/<cast_name>.SADCP_EXTRACT.mat`, and the endpoint returns the resulting `data`-mount-relative path, which the frontend uses to fill the existing `sadcp` field — the same handoff mechanic the CTD quick-convert flow already uses for the `ctd` field. The `sadcp` field's existing behavior (plain browse/type-a-path, verbatim into `f.sadcp` in the generated `set_cast_params.m`) is completely unchanged; this is an additional way to populate it, not a replacement.

**New UI:** an "Extract from CODAS output" button next to the existing SADCP field, shown only when the `codas` mount is present, opening a file-browser panel (reusing the existing browser widget) scoped to that mount.

## Error handling

`SadcpExtractError` (mirrors `QuickConvertError`), raised for:

- The `.nc` file not found, or not readable as a valid NETCDF3 file.
- Missing one or more of the expected variables (`time`, `lon`, `lat`, `u`, `v`, `depth`), with a message naming which are missing — guards against the wrong file being selected.
- Zero ensembles found within the cast's time window plus buffer — message suggests checking that the ADCP was actually logging during the cast, or that the right instrument/`.nc` file was selected (per `nuyina_uhdas_codas`'s own README, the real Nuyina ADCP has in practice sat off for extended periods).
- Non-constant `depth` bins across the selected ensembles.

All of these surface as a clear error in the UI, the same way `QuickConvertError` does for the CTD flow today — this feature never silently produces a `.mat` file with wrong or partial data.

## Testing

- `webapp/sadcp_extract.py`'s logic is unit-tested with small synthetic NETCDF3 fixtures, built in-test with `scipy.io.netcdf_file` in write mode (no real CODAS output needed) — covering: correct Julian-day conversion (checked against known calendar dates), correct `(depth, time)` transposition, fill-value-to-`NaN` conversion, the zero-ensembles-in-window error path, and the non-constant-depth error path.
- UI wiring (mount visibility, browse panel, field fill-in) is verified manually against a running server, same pattern used for the CTD quick-convert UI work — no live CODAS data is required; a small hand-built fixture `.nc` is enough.
- No accuracy/validation suite is in scope, since this feature performs no calibration of its own — it reformats and slices an already-processed CODAS product.

## Explicitly out of scope

- Any calibration, editing, or recalculation of ADCP velocities — that is `nuyina_uhdas_codas`'s (and upstream CODAS's) responsibility entirely. This feature only reads already-processed output.
- Automatic, cruise-level extraction (point at a voyage's CODAS root once, auto-slice every cast). Deferred; revisit if the manual per-cast flow proves the pattern is useful.
- Multi-instrument auto-selection or merging (e.g. combining `os150nb` and `os38nb`). The user picks a single `.nc` file per extraction, same as picking any other single input file elsewhere in this form.
- Folding `nuyina_uhdas_codas` into this repo, or vice versa — considered and rejected above.
- A user-configurable time-window buffer. The fixed 3-hour default can be revisited later if real usage shows it needs adjusting.
