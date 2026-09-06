# Patches applied to LDEO_IX for Octave compatibility

`ldeo_ix/` is the LDEO_IX LADCP processing source (see `NOTICE.md` for
provenance), patched only where needed to run under GNU Octave 9.2 instead
of MATLAB. Every change is listed here; nothing else was touched.

## Genuine bugs fixed to get the pipeline running

1. **`getinv.m`**: `do` used as a plain variable name (`do=d;` / `de.do=do;`).
   `do` is a reserved keyword in Octave (`do ... until`), a valid identifier
   in MATLAB. Renamed the *variable* to `d_orig` (the struct field name
   `de.do` is untouched — field names aren't keyword-restricted). Two-line
   change, no behavior difference.

2. **`plotraw.m`**: same class of bug — `function checkbeam(t,ax,do)` uses
   `do` as a function parameter. Renamed to `is_bottom` (call sites use
   positional args only, so this is a safe, local rename).

3. **`loadnav.m`**: a real, pre-existing bug, not introduced here. Its own
   `setdefv()` call (line 72) defaults `nav_time_base` onto the `p` struct,
   but the `switch` that consumes it (line 137) reads `f.nav_time_base` —
   with only `p.nav_time_base` set, this dies with "structure has no member
   'nav_time_base'". `loadctd.m`'s changelog (line 85) shows the *identical*
   `ctd_time_base` bug was fixed on 2014-03-21 (default moved from `p` to
   `f`); the fix was apparently never ported to `loadnav.m`. **Not patched
   in `loadnav.m` itself** — set `f.nav_time_base` directly in your own
   `set_cast_params.m` (see `examples/`) as a workaround.

4. **`loadrdi.m`**: a real, pre-existing bug, not introduced here. The
   no-flow-gradient ("dead instrument") check in both the down-looker and
   up-looker branches computed `dru` and `drv` correctly but then tested
   `dru` twice, never `drv` — so a cast with a genuinely dead v-component
   would pass the check unnoticed. Originally left unpatched here so this
   image's output could be diff-checked against published data processed
   with the unmodified upstream MATLAB version; that comparison is long
   done, and leaving the bug in was an oversight rather than a deliberate
   choice. Now patched (two occurrences, around lines 478 and 500):

   ```
   -nbad=find(abs(drw)<0.005 & abs(dru)<0.005 & abs(dru)<0.005);
   +nbad=find(abs(drw)<0.005 & abs(dru)<0.005 & abs(drv)<0.005);
   ```

5. **`end_processing_step.m`**: the original checkpoint-save idiom
   (`eval(sprintf('save %s_%d', f.checkpoints, pcs.cur_step))`) has no
   `.mat` extension. MATLAB's `save name` auto-appends `.mat`; Octave's does
   not. `begin_processing_step.m`'s `load(sprintf('%s_%d.mat', ...))`
   expects the extension, so checkpoint resume silently failed until this
   was fixed to `save %s_%d.mat`.

6. **`loadnav.m`**: a real, pre-existing bug, not introduced here. The
   `magdec`-not-found fallback branch (around line 269, `if ~isfinite(p.drot)`)
   builds a warning message with
   `sprintf('"magdec" not found; using old magdev code with IGRF00',f.IGRF)`
   — `f.IGRF` is never assigned anywhere in `default.m` or any
   `set_cast_params.m`, and the format string has no `%s` placeholder for it
   anyway (so the argument was always dead, never actually used even when it
   existed). Referencing the unset field crashes Octave
   (`error: structure has no member 'IGRF'`) before ever reaching the very
   next line, the actually-working fallback
   `p.drot = magdev(medianan(d.slat),medianan(d.slon));`. This is not merely
   theoretical: it crashed step 3 (LOAD GPS DATA) of a real Nuyina LADCP cast
   005 processing run on 2026-09-06 (this Docker image ships no `magdec`
   binary, so any cast whose `set_cast_params.m` doesn't already set a finite
   `p.drot` hits this path) — see
   `.superpowers/sdd/2026-09-06-nuyina-ladcp-cast-processing/task-3-report.md`
   and `task-4-report.md`. Fixed by removing the dead `, f.IGRF` argument —
   behavior-preserving, since the format string never consumed it. (The
   sibling `if s == 1` branch, taken when `magdec` *is* found, calls
   `geomag(...)` — a local subfunction defined further down in this same
   file, not a missing `geomag.m`, so it resolves fine; it would still fail
   in this image, but via `geomag`'s own `error(['cannot execute <' CMD
   '>'])` when it re-invokes the missing `magdec` binary, not via an
   undefined-function/undefined-field error.)

## Upstream contact

The `loadnav.m` (`nav_time_base`) and `loadrdi.m` (`drv`) bugs above were
reported to Andreas Thurnherr, the current maintainer of LDEO_IX, on
2026-09-03. He confirmed on 2026-09-04 that both are real and will be
folded into upstream — including a successor version he is developing,
tentatively named LDEO_XI, not yet published. Nothing here depends on that
future release; noted so a later session doesn't have to re-derive whether
these were genuine bugs from scratch.

## Missing/incompatible functions — fixed via `stubs/`

The upstream source does not contain `makebars.m` anywhere (genuinely
missing, not an Octave/MATLAB API difference) — used by `plotraw.m` for a
diagnostic bar overlay. Stubbed with harmless placeholder output.

`interp1q` is a MATLAB builtin not implemented in Octave (confirmed against
`gnuoctave/octave:9.2.0`) — stubbed as a thin wrapper over
`interp1(..., 'linear')`.

All other stubs are pure no-op plotting functions, since this image has no
display: `figure`, `plot`, `subplot`, `hold`, `axis`, `title`, `xlabel`,
`ylabel`, `text`, `legend`, `colorbar`, `pcolor`, `contourf`, `streamer`,
`orient`, `print`, `pause`, `clf`, `gca`, `grid`, `colormap`, `imagesc`,
`shading`, `fill`, `caxis`, `bar`, `axes`. `set.m` is the one exception with
real logic: it no-ops only when called on a numeric (graphics-handle) first
argument, falling through to `builtin('set', ...)` otherwise — so
non-graphics uses of `set()` still work.

None of these stubs change any numerical result — they only silence a
diagnostic-plotting subsystem that needs a display MATLAB would have and
this headless image doesn't.

## Version note

`ldeo_ix/default.m` reports `Version IX_14beta`. This is the upstream
version as received; it has not been changed here.
