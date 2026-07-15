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

4. **`end_processing_step.m`**: the original checkpoint-save idiom
   (`eval(sprintf('save %s_%d', f.checkpoints, pcs.cur_step))`) has no
   `.mat` extension. MATLAB's `save name` auto-appends `.mat`; Octave's does
   not. `begin_processing_step.m`'s `load(sprintf('%s_%d.mat', ...))`
   expects the extension, so checkpoint resume silently failed until this
   was fixed to `save %s_%d.mat`.

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
