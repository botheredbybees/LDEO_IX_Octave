# `magdec` Replacement — Design

Status: Draft

## Context

`ldeo_ix/loadnav.m` (lines 264-352) shells out to an external command-line tool, `magdec`, to
compute magnetic declination for a cast from its real GPS navigation. This tool is not bundled
with `ldeo_ix/` in this repo — Andreas Thurnherr's own manual for the software (fetched and read
this session) says it's Eric Firing's `geomag`/`magdec`, historically distributed as a `geomag/`
subdirectory of the official LDEO_IX distribution. When `magdec` isn't found, `loadnav.m` falls
back to `magdev.m`, which hardcodes the year-2000 IGRF00 model regardless of the cast's real date.

Every real Nuyina cast processed this session (2024 data, three casts across the earlier
generic-cast-processing-script plan) silently took this fallback path — confirmed via each run's
own log (`"magdec" not found; using old magdev code with IGRF00`) and flagged by that plan's final
whole-branch review as a real, materially larger accuracy issue than a separately-found and
already-fixed navigation-table-windowing bug (two to three orders of magnitude larger, per that
review's own estimate).

This session live-checked all three real channels that could plausibly still serve the original
`magdec`/`geomag` source, and found all three dead:

- SOEST's old hgweb (the URL referenced in `ldeo_ix/loadnav.m`'s own `geomag()` subfunction
  comment) — `404 Not Found`.
- `ftp.ldeo.columbia.edu` (where Thurnherr's manual says the distribution, including `geomag/`,
  actually lives) — connection refused on port 21.
- Thurnherr's own current "Software" link on his live faculty page
  (`https://www.ldeo.columbia.edu/cgi-bin/ladcp-cgi-bin/hgweb.cgi`) — reachable, but returns a
  genuine `500 Internal Server Error` on every path tried (`/`, `/geomag/`, `/LDEO_IX/`), i.e. the
  CGI script itself is broken server-side, not merely moved.

With no live path to the historically-validated original tool, this design replaces it with a
small, original, from-scratch `magdec` implementation built on a maintained, real IGRF library,
rather than continuing to depend on a source that no longer exists anywhere reachable.

## Goal

Install a real `magdec` command on the Docker image's `$PATH` that `ldeo_ix/loadnav.m` picks up
correctly, computing magnetic declination from the actual current IGRF model for the cast's real
date and position — closing the silent year-2000-fallback gap found this session.

## The exact contract (verified directly against `ldeo_ix/loadnav.m`, not assumed)

`loadnav.m:264-272`:

```matlab
if ~isfinite(p.drot)		      % set magdecl
 [s,o] = system('magdec');
 if s == 1
   p.drot = geomag(f,meannan(d.navtime_jul),medianan(d.slat),medianan(d.slon));
 else
   warn = sprintf('"magdec" not found; using old magdev code with IGRF00');
   ...
   p.drot = magdev(medianan(d.slat),medianan(d.slon));
 end
```

`loadnav.m:332-364`'s local `geomag()` subfunction, when the branch above is taken:

```matlab
CMD = sprintf('magdec %g %g %d %d %d',lon,lat,year,month,day);
[status,work] = system(CMD);
if status ~= 0
	error(['cannot execute <' CMD '>']);
end
vals = sscanf(work,'%g');
if length(vals) ~= 4
	error(['unexpected output from <' CMD '>']);
end
dev = vals(1);
```

This gives two hard, load-bearing requirements, independently confirmed by Thurnherr's own manual
("test the program by executing the Matlab command `system('magdec')`, which should not produce
an error and return a value of 1"):

1. **Called with zero arguments** (the existence probe), `magdec` must exit with status **exactly
   1** — not 0, not any other value. This is what selects the real-computation branch over the
   year-2000 fallback.
2. **Called with five arguments** (`magdec <lon> <lat> <year> <month> <day>`), it must exit **0**
   and print at least 4 whitespace-separated numbers to stdout, the **first** being declination in
   degrees. Only `vals(1)` is ever read by `loadnav.m` — the other three exist for output-shape
   compatibility with the original tool.

**Sign convention**, confirmed against the existing `magdev.m` fallback (`ldeo_ix/magdev.m`, via
its `dihf` conversion): declination is `atan2(Y, X)` where X is the geomagnetic-north field
component and Y is the geomagnetic-east component — positive means magnetic north is east of true
north. The replacement must use the identical convention, or every declination this pipeline
computes flips sign silently.

## Library choice: `ppigrf`

[`ppigrf`](https://github.com/IAGA-VMOD/ppigrf) — MIT-licensed, pip-installable (`pip install
ppigrf`), pure Python (no Fortran/compiled dependency), maintained by IAGA-VMOD (the actual
IAGA Working Group on Geomagnetic Field Modelling — the organization that publishes IGRF itself),
currently defaulting to IGRF-14 (the 2025 generation). Its only public API relevant here:

```python
Be, Bn, Bu = ppigrf.igrf(lon, lat, h, date)   # East, North, Up field components in nT, geodetic
```

It has no dedicated declination function — this design derives it directly:
`declination = atan2(Be, Bn)` in degrees (Be=east, Bn=north — the same X=north/Y=east convention
as `magdev.m`, just with the axis names swapped to match `ppigrf`'s own East/North ordering).
Inclination, horizontal intensity, and total intensity (the conventional remaining 3 values a real
`geomag`-family tool reports) are cheap to compute from the same three components and are included
for a complete, honest 4-number output, even though `loadnav.m` only reads the first.

## Architecture

**New top-level directory `magdec/`** (parallel to `stubs/`, `webapp/` — not inside `stubs/`,
which is specifically for Octave-path-shadowing no-op M-files for headless plotting, a different
mechanism entirely from installing a real shell-`$PATH` binary):

- `magdec/magdec.py` — the tool itself. A `compute(lon, lat, year, month, day) -> tuple[float,
  float, float, float]` pure function (declination, inclination, horizontal intensity, total
  intensity) plus a thin `main(argv) -> int` CLI dispatcher implementing the exact 0-arg/5-arg
  contract above. Mirrors the existing `convert()`/`main()` split already used in this repo's
  `scripts/gngga_to_navtable.py`.
- `magdec/requirements.txt` — `ppigrf`.
- `magdec/test_magdec.py` — real unit tests (no mocking `ppigrf` — it's fast, pure Python, and
  mocking it would only test the arithmetic, not that this script calls it correctly).

**Dockerfile**: one new `pip3 install -r magdec/requirements.txt` step (alongside the existing
webapp requirements install), `COPY magdec/magdec.py /usr/local/bin/magdec`, `RUN chmod +x
/usr/local/bin/magdec`. `/usr/local/bin` is already on the base `gnuoctave/octave:9.2.0` image's
`$PATH`, so no `ENV PATH` change is needed — Octave's `system()` calls a real shell, which
resolves it there directly.

## `magdec.py` behavior

```python
#!/usr/bin/env python3
"""magdec -- CLI replacement for Eric Firing's original magdec tool that
ldeo_ix/loadnav.m's geomag() subfunction shells out to. Uses ppigrf
(IGRF-14, IAGA-VMOD) instead of the original tool's own bundled model,
since every official distribution channel for the original binary is
unreachable as of 2026-09-06 (see CHANGES.md).

Two calling conventions, both dictated by ldeo_ix/loadnav.m's own logic
(NOT a general-purpose CLI design choice -- see docs/superpowers/specs/
2026-09-06-magdec-replacement-design.md):
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
from datetime import date


def compute(lon: float, lat: float, year: int, month: int, day: int) -> tuple:
    import ppigrf

    Be, Bn, Bu = ppigrf.igrf(lon, lat, 0.0, date(year, month, day))
    Be, Bn, Bu = float(Be), float(Bn), float(Bu)
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

`Bu` is up-positive (ppigrf's geodetic convention); standard inclination uses down-positive Z, so
`inclination = atan2(-Bu, horizontal)`, not `atan2(Bu, horizontal)` — a real sign detail worth
getting right even though `loadnav.m` never reads this value, since a wrong inclination would be a
silent correctness bug in the "output-shape parity" half of this tool's contract.

## Testing

`magdec/test_magdec.py`, run via `.venv312/bin/python -m pytest magdec/test_magdec.py` (needs
`ppigrf` installed into `.venv312` — add `magdec/requirements.txt` to whatever install step
provisions that venv, or install it directly as part of the plan's own testing task):

- `compute()` returns finite, plausible values for a known real location (e.g. Hobart,
  `lon≈147.3, lat≈-42.9`) — declination within a sane real-world range (roughly ±30° is generous
  for anywhere on Earth), inclination within [-90, 90], horizontal/total intensity positive and in
  a plausible nT range (tens of thousands, not zero or astronomically large).
- `main()` with zero args: exit code 1, usage text on stderr, nothing on stdout.
- `main()` with five valid args: exit code 0, stdout is exactly 4 whitespace-separated floats.
- `main()` with a wrong arg count (e.g. 3): exit code 1, matching the zero-arg case's safe
  default.
- **Sign-convention cross-check against the existing `magdev.m` fallback**: for the same real
  lat/lon, `compute()`'s declination and `magdev.m`'s year-2000 IGRF00 declination should be the
  same *sign* and roughly the same order of magnitude (secular variation over ~25 years is real
  but bounded — a flipped sign or wildly different magnitude means an `atan2` argument-order bug
  in `compute()`, not a genuine model difference). Running `magdev.m` itself requires Octave; this
  check can either shell out to a throwaway `octave-cli` invocation from the test, or use an
  already-known real value from this session's own investigation (real `magdev` output for one of
  this session's actual cast positions is already recorded in the earlier plan's ledger/reports)
  as a fixed expected-sign/order-of-magnitude comparison instead of invoking Octave from a Python
  test.

## Verification (live, real infrastructure)

1. `.venv312/bin/python -m pytest magdec/test_magdec.py` — new tests pass.
2. `.venv312/bin/python -m pytest webapp/tests scripts/test_gngga_to_navtable.py` — still 114
   passed, unaffected (this change touches neither directory).
3. Rebuild the image: `docker build -t ldeo-ix-octave .` (and re-tag `ldeo-ix-octave:local` /
   `:latest` as this session's earlier work already established, so both tags used by
   `scripts/process_cast.sh` and its Nuyina-specific callers stay current).
4. `docker run --rm ldeo-ix-octave magdec; echo "exit: $?"` — confirm exit code is exactly `1`.
5. `docker run --rm ldeo-ix-octave magdec 147.3 -42.9 2024 6 17` — confirm exit `0` and a
   plausible-looking 4-number line. Spot-check the declination value against one independent
   real-world source (e.g. NOAA's public online magnetic-declination calculator for the same
   position/date) to sanity-check `ppigrf` itself is producing scientifically correct output, not
   just internally self-consistent output.
6. Re-run cast 005 through `scripts/process_cast.sh` against the existing
   `nuyina_data/202324050_005/` staging directory (the same real data this session already used
   twice) and confirm, via the real Octave log output, that `loadnav.m` now takes the `geomag()`
   branch — no more `"magdec" not found` warning — and that the resulting `p.drot` differs from
   this session's repeatedly-observed fallback value (`15.057159`), consistent with a genuinely
   different (2024 IGRF-14 vs. year-2000 IGRF00) computation having actually run.

## Documentation

- **`CHANGES.md`**: a new entry documenting that a `magdec` replacement is now built into the
  image, closing the gap the earlier session's entry flagged ("this Docker image ships no `magdec`
  binary"). Not a patch to `ldeo_ix/`'s own files — this restores the *integration point*
  `loadnav.m` already expects, without modifying any upstream `.m` file — but still worth a
  `CHANGES.md` line for the same transparency reason this repo already documents Octave
  compatibility patches.
- **`README.md`**: a short new subsection (near the existing "Why Octave instead of MATLAB"
  section, or wherever reads naturally) noting the image includes a real `magdec` command backed
  by `ppigrf`/IGRF-14, and why (the original tool's distribution is currently unreachable). This is
  scientifically material provenance information for anyone relying on this pipeline's declination
  correction, not merely an implementation detail — unlike `scripts/process_cast.sh`'s internals,
  which stayed undocumented at this level since they're transparent to the tool's users.
- **`NOTICE.md`**: one new line for `ppigrf` (MIT), matching the existing pattern already used for
  `ctdam`/`seabirdscientific` (pip dependencies with real license implications get a line; `ppigrf`
  is MIT like this repo's own packaging license, so the entry is for consistency/completeness
  rather than because of any license conflict).

## Non-Goals

- Re-attempting to locate or vendor the original Eric Firing `magdec`/`geomag` source — all three
  known distribution channels are confirmed dead as of this session; if one becomes reachable again
  later, that would be a separate, future decision (swap back, or keep this replacement — not
  decided here).
- Emailing Andreas Thurnherr to ask for the source directly — a real option raised during this
  session's exploratory discussion, but the user chose to build a self-contained replacement
  instead, explicitly to avoid depending on a source with an uncertain future.
- Any change to `scripts/process_cast.sh`'s public interface or `docs/vessel-data-preparation.md`
  — this fix is transparent to that script's callers; nothing about the `cast-config.json` contract
  or the staging-directory layout changes.
- Re-running casts 004/006 (only cast 005 is re-verified, per the Verification section above) —
  one real end-to-end confirmation is sufficient to prove the mechanism works; re-running all three
  would be repeating the same proof three times for no new information.
