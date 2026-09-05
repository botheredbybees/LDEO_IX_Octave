# SADCP Conversion from CODAS Output

**Date:** 2026-09-06 (revised)
**Status:** Approved for planning
**Source of truth:** `LDEO_IX_Octave/docs/superpowers/specs/2026-09-06-sadcp-codas-extract-design.md` (GitHub, `botheredbybees/LDEO_IX_Octave`) — this page is a published copy for team visibility, not the canonical edit location.

## Revision note

The original version of this spec designed a bespoke per-cast time-window extractor reading CODAS's "short form" netCDF output. Mid-design, `ldeo_ix/mkSADCP.m` was found — a script by Andreas Thurnherr (LDEO_IX's own maintainer) already shipped in this repo, purpose-built for exactly this conversion. It works differently from what was first designed, and more simply:

- It reads CODAS's native `contour_xy.mat`/`contour_uv.mat` pair (from the CODAS `contour/` output directory), not the netCDF short form.
- It converts the **whole voyage** in one pass, once (or once per CODAS reprocessing) — not per cast. Its own header comment says as much: "during ship-board processing, this script will be called near the beginning of `set_cast_params.m`." Per-cast time windowing already happens at *runtime*, inside `loadsadcp.m` itself, via `p.time_start`/`p.time_end`/`p.sadcp_dtok`.
- `contour_uv.mat`'s `uv` array is already laid out `(depth, time)` (with `u`/`v` interleaved column-wise) — no transpose needed. `contour_xy.mat` even carries its own `year_base` variable, so the conversion needs no external metadata lookup at all.

This revision replaces the bespoke design with a direct Python port of `mkSADCP.m` — same inputs, same transform, same output. Reinventing this would just be a worse version of a tool that already exists and is already trusted by the LADCP community; the only new work is exposing it through the webapp instead of requiring a MATLAB/Octave shell session.

## Context

`ldeo_ix/loadsadcp.m` reads the cast's shipboard-ADCP (SADCP) reference field, `f.sadcp`, via a plain `load(f.sadcp)`. It expects a MATLAB/Octave `.mat` file already containing `tim_sadcp`, `lat_sadcp`, `lon_sadcp`, `u_sadcp(z,t)`, `v_sadcp(z,t)`, and `z_sadcp(z,1)` — i.e. an already-processed underway ADCP velocity time series, not a raw instrument file. Today the webapp's `sadcp` field is a plain browse/type-a-path input (`webapp/models.py`, `webapp/config.py`'s `sadcp` mount) with no logic behind it: the user is expected to already have a suitable `.mat` file from somewhere else.

The sister project `nuyina_uhdas_codas` runs the University of Hawaii's CODAS processing pipeline against RSV *Nuyina*'s shipboard ADCP. Among its output, per instrument (e.g. `os150nb`), is a `contour/` directory containing `contour_xy.mat` (position/time: `xyt`, `zc`, `year_base`) and `contour_uv.mat` (velocities: `uv`) — CODAS's native matfile export, and exactly what `mkSADCP.m` was written to consume. No calibration is redone by this feature; it only reformats an already-trustworthy product, the same way `mkSADCP.m` always has.

A separate idea raised during design — folding `LDEO_IX_Octave` and `nuyina_uhdas_codas` into a single project — was considered and rejected (by the user, immediately): the two have incompatible dependency footprints (a minimal Octave image vs. a heavy compiled toolchain), incompatible lifecycles (on-demand per-cast batch vs. a continuous 5-minute cron process against live ship data), and separate licensing-provenance stories (`NOTICE.md`'s careful `ldeo_ix`-only no-license disclosure vs. `pycurrents`/`codas3`/`onship`, whose licenses have not been reviewed). The two repos stay separate; this feature is the narrow interface between them — a documented file format, not shared code or infrastructure.

## Decision

Add a manual, opt-in conversion step to the webapp: the user browses to a CODAS instrument's `contour/` output directory (from wherever `nuyina_uhdas_codas`'s output is mounted), and the webapp runs the same transform `ldeo_ix/mkSADCP.m` does, producing one `.mat` file covering the whole voyage. That file's path then fills the existing `sadcp` field, the same way for every cast in the cruise — there is no per-cast parameter to this conversion (no time window, no buffer), matching how `mkSADCP.m` itself is meant to be used.

This entire feature is optional infrastructure: the `sadcp` field, and SADCP data generally, are already optional in LDEO_IX (`loadsadcp.m` only runs `if existf(f,'sadcp')==1`). The new UI only appears when a new `codas` mount is actually present, following the same `available_mounts()` pattern every other mount already uses — a cruise/machine with no `nuyina_uhdas_codas` data mounted sees nothing different from today.

The conversion button lives in the same place the original design put it — next to the per-cast SADCP field, mirroring the CTD quick-convert button's location — purely because that's where file-browsing for this field already happens in the UI, not because the operation is actually per-cast. In practice a user runs it once for the voyage (or again after CODAS reprocessing) and then points every cast's `sadcp` field at the same resulting file, exactly as they would with any pre-existing `.mat` file today.

## Architecture

**New module:** `webapp/sadcp_convert.py`, pure-logic, parallel to `webapp/quick_convert.py`. A direct port of `ldeo_ix/mkSADCP.m`'s logic:

- Reads `contour_xy.mat` and `contour_uv.mat` from the given directory via `scipy.io.loadmat` — already a project dependency (`scipy` is already required; only the `loadmat`/`savemat` entry points are new uses of it, no new dependency).
- Validates both files are present and contain the expected variables (`xyt`, `zc`, `year_base` in `contour_xy.mat`; `uv` in `contour_uv.mat`), to catch a user pointing at the wrong directory.
- `lon_sadcp, lat_sadcp, dday = xyt[0], xyt[1], xyt[2]`; `z_sadcp = zc` (already a single column vector, needing no per-ensemble constancy check the way a netCDF-derived source would).
- `u_sadcp = uv[:, 0::2]`, `v_sadcp = uv[:, 1::2]` — already `(depth, time)`, no transpose.
- Drops columns/entries where `dday`, `lat_sadcp`, or `lon_sadcp` is `NaN` (mirroring `mkSADCP.m`'s `badi` filter).
- Normalizes longitude into `[-180, 180)` (mirroring `mkSADCP.m`'s subtract-360-then-rewrap dance, expressed directly as `((lon + 180) % 360) - 180`).
- `tim_sadcp = to_julian_day(year_base, 1, 1, 0) + dday`, using the same absolute Julian day number convention as `ldeo_ix/julian.m` — the one piece of numeric logic worth its own unit test against known calendar dates (unchanged from the original design).
- Writes `tim_sadcp`, `lat_sadcp`, `lon_sadcp`, `u_sadcp`, `v_sadcp`, `z_sadcp` via `scipy.io.savemat` (MATLAB v5 format, which Octave's `load()` reads natively) — the exact variable set `mkSADCP.m` saves.

**New mount:** `config.py` gets a `"codas": Path(os.environ.get("LDEO_CODAS_DIR", "/codas_data"))` entry, following the existing mount-config pattern exactly. Like every other mount, it is only offered by `available_mounts()` (and therefore only shown in the UI) when the directory actually exists.

**New endpoint:** `POST /api/sadcp/convert` — body `{contour_dir}`, resolved/validated the same way the existing `POST /api/quick-convert/ctd` endpoint resolves its inputs (`paths.resolve_within` against the `codas` mount). No cast-specific input is needed at all — the endpoint is fully stateless. Deliberately **not** placed under `/api/quick-convert/`, to avoid implying this skips real processing the way the CTD hex fallback does; it doesn't skip anything `mkSADCP.m` itself wouldn't.

Output is written to `{data_mount_root}/sadcp_convert/<instrument-dir-name>.SADCP.mat` (the instrument directory name, e.g. `os150nb`, taken from `contour_dir`'s parent — `contour_dir` itself is always named `contour`). The endpoint returns the resulting `data`-mount-relative path, which the frontend uses to fill the `sadcp` field — the same handoff mechanic the CTD quick-convert flow already uses for the `ctd` field. The `sadcp` field's existing behavior (plain browse/type-a-path, verbatim into `f.sadcp` in the generated `set_cast_params.m`) is completely unchanged; this is an additional way to populate it, not a replacement.

**New UI:** a "Convert CODAS SADCP data" button next to the existing SADCP field, shown only when the `codas` mount is present, opening a file-browser panel (reusing the existing browser widget) scoped to that mount, for picking the `contour/` directory.

## Error handling

`SadcpConvertError` (mirrors `QuickConvertError`), raised for:

- `contour_xy.mat` or `contour_uv.mat` not found in the given directory, or not readable as valid MATLAB files.
- Missing one or more of the expected variables, with a message naming which are missing — guards against pointing at the wrong directory (e.g. the instrument root instead of its `contour/` subdirectory).
- Zero valid (non-`NaN`) time/position entries after filtering — message suggests checking that the ADCP was actually logging during the voyage (per `nuyina_uhdas_codas`'s own README, the real Nuyina ADCP has in practice sat off for extended periods).

All of these surface as a clear error in the UI, the same way `QuickConvertError` does for the CTD flow today — this feature never silently produces a `.mat` file with wrong or partial data.

## Testing

- `webapp/sadcp_convert.py`'s logic is unit-tested with small synthetic `contour_xy.mat`/`contour_uv.mat` fixtures, built in-test with `scipy.io.savemat` (no real CODAS output needed) — covering: correct Julian-day conversion (checked against known calendar dates), correct `u`/`v` de-interleaving, longitude normalization (both an already-normal case and a >180°-wraparound case), the `NaN`-filtering path, and both missing-file/missing-variable error paths.
- UI wiring (mount visibility, browse panel, field fill-in) is verified manually against a running server, same pattern used for the CTD quick-convert UI work — a small hand-built fixture pair of `.mat` files is enough, no live CODAS data required.
- No accuracy/validation suite is in scope, since this feature performs no calibration of its own and its transform is a direct port of an already-trusted tool (`mkSADCP.m`) — the tests confirm the port matches that tool's own logic, not that the underlying science is correct.

## Explicitly out of scope

- Any calibration, editing, or recalculation of ADCP velocities — that is `nuyina_uhdas_codas`'s (and upstream CODAS's) responsibility entirely. This feature only reads already-processed output.
- Any per-cast time-window logic. `loadsadcp.m` already does this at runtime; duplicating it here would be redundant at best and a source of divergence at worst.
- Multi-instrument auto-selection or merging (e.g. combining `os150nb` and `os38nb`). The user picks a single instrument's `contour/` directory per conversion, same as picking any other single input elsewhere in this form.
- Folding `nuyina_uhdas_codas` into this repo, or vice versa — considered and rejected above.
- Reading CODAS's "short form" netCDF output. It was the original design's data source but is not what `mkSADCP.m` uses, and the `.mat` pair is simpler to work with (no transpose, self-contained `year_base`) and closer to the tool's own well-established behavior.
