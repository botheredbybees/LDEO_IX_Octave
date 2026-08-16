**Status as of 2026-08-16: drafts only.** Both fix branches
(`octave-portability-fixes`, `fix-nav-time-base-and-gradient-swap`) are
pushed to `botheredbybees/LDEO_IX` (a fork of `athurnherr/LDEO_IX`), but
**no PR or issue has been opened against upstream yet** — nothing here is
visible to the upstream maintainer until Peter reviews these drafts and
says go.

---

# Draft 1 — PR: octave-portability-fixes

**Title:** Octave compatibility: rename reserved-keyword variable, fix checkpoint file extension

**Body:**

Found while packaging LDEO_IX to run under GNU Octave instead of MATLAB (so people without a MATLAB license can still process LADCP data — https://github.com/botheredbybees/LDEO_IX_Octave). Both fixes are portability-only, zero behavior change under MATLAB, verified against Octave 9.2.0.

1. **`getinv.m` / `plotraw.m`** — `do` is a reserved keyword in GNU Octave (`do ... until` loops) but a valid identifier in MATLAB. `getinv.m` used it as a plain variable (`do=d;` ... `de.do=do;`), and `plotraw.m`'s `checkbeam()` used it as a function parameter. Both fail to *parse* under Octave, which blocks the entire pipeline — `getinv.m` is the inverse solver, not an optional path. Renamed to `d_orig` / `is_bottom` respectively; the `de.do` struct *field* name is untouched since field names aren't keyword-restricted in either language.
2. **`end_processing_step.m`** — the checkpoint-save idiom (`save %s_%d`, no extension) relies on MATLAB's `save name` auto-appending `.mat`. Octave's `save` does not auto-append, so the file this writes doesn't match what `begin_processing_step.m` later loads (`%s_%d.mat`) — silently breaking checkpoint resume under Octave. Added the extension explicitly; this matches the extension `begin_processing_step.m` already expects, so it's a no-op change under MATLAB too.

Verified: full pipeline now parses and runs under Octave 9.2.0; checkpoint save/load round-trips correctly.

Branch: `octave-portability-fixes`

---

# Draft 2 — PR: fix-nav-time-base-and-gradient-swap

**Title:** Fix nav_time_base struct mismatch (loadnav.m) and swapped gradient-test variables (loadrdi.m)

**Body:**

Two independent correctness bugs found while cross-checking LDEO_IX's output stage-by-stage against an independent from-scratch reimplementation.

**1. `loadnav.m`: `nav_time_base` default set on the wrong struct**

`setdefv()` defaults `nav_time_base` onto `p` (line 82), but every consumer reads `f.nav_time_base` (the `switch` around line 147, the check around line 196). Unless a cast's `set_cast_params.m` explicitly sets `f.nav_time_base` itself, the switch errors with "structure has no member 'nav_time_base'".

`loadctd.m`'s own changelog records the *identical* bug for `ctd_time_base`, fixed on 2014-03-21 ("moved ctd_time_base from p. to f."). That fix appears to have never been ported to `loadnav.m`. This PR applies the same fix by the same pattern.

**2. `loadrdi.m`: non-pinging/dead-instrument check never tests the u-gradient**

```matlab
drw=medianan(abs(diff(d.rw(d.izd,:))));
dru=medianan(abs(diff(d.rv(d.izd,:))));     % <- named dru, computed from rv
drv=medianan(abs(diff(d.ru(d.izd,:))));     % <- named drv, computed from ru
nbad=find(abs(drw)<0.005 & abs(dru)<0.005 & abs(dru)<0.005);
%                                            ^^^^^^^^^ dru tested twice
```

The variable names are swapped relative to what they hold (`dru` holds the **v**-gradient, `drv` holds the **u**-gradient), and the `find()` condition tests `dru` twice, `drv` never — so the u-velocity bin-to-bin gradient plays no part in flagging dead/non-pinging ensembles, only w and v do. Identical pattern in both the downlooker block (~line 479) and the uplooker block (~line 501). Fixed to test all three components, matching what the code evidently intends.

**Impact:** on our validation cast (GO-SHIP P16N 2015, cast 003) this changed which ensembles get flagged as non-pinging, with negligible effect on the final velocity solution there — but the code as written doesn't implement its own evident intent, and I'd expect other casts (especially ones with real u-only anomalies) to be more sensitive to it than ours was. Flagging clearly since this does change numeric output on some casts, unlike the portability-only PR — happy to discuss whether you'd want a version bump alongside it.

Branch: `fix-nav-time-base-and-gradient-swap`

---

# Draft 3 — Issue: licensing clarification + informational findings

**Title:** License clarification request, + a few documentation/portability observations from porting

**Body:**

Hi Andreas (or whoever's picking this up) — thanks for maintaining LDEO_IX and keeping it public on GitHub.

**Main ask: what license applies to this repository?** I've been packaging LDEO_IX into a Docker image so people without a MATLAB license can still run it under GNU Octave (https://github.com/botheredbybees/LDEO_IX_Octave — the two PRs I've just opened came out of that work). There's no `LICENSE` file here and I haven't found a license statement anywhere else in the source or the accompanying manual — just the general "use at your own risk" framing common in oceanographic software distribution. I'd like to redistribute the packaged image publicly (Docker Hub) with the terms clearly stated rather than left ambiguous, so: would you be willing to add an explicit license (even something permissive and simple), or at least confirm in writing what terms you're comfortable with for redistribution/reuse? Happy to work with whatever you prefer.

**A few smaller things noticed along the way, not urgent, no action needed unless useful:**

- `sounds.m`'s header comment documents a check value of `SVEL=1731.995` for `S=40, T=40, P=10000`, but running the function as written gives `1732.139394` — about 0.14 m/s off. Might be a coefficient that drifted in the original FORTRAN→MATLAB translation, or just a stale comment; didn't try to isolate which.
- `prepinv.m` calls `outlier()` on super-ensembles for bottom-track editing, but `outlier.m`'s bottom-track branch gates on `size(dummyb,2)==4` — true when called from `loadrdi.m` (its original context, `bvel` is `(n_ens,4)`), false when called from `prepinv.m` (`bvel` is `(4,n_se)` there). So bottom-track outlier editing of super-ensembles silently never runs. Might be intentional (a coincidental guard that happens to do the right thing) or might be dead code that was meant to run — not obvious from the code alone which one, so flagging rather than guessing.
- `plotraw.m` calls `makebars()`, which isn't present anywhere in the IX_15 distribution — cosmetic (diagnostic-plot only) but it does make a default full run error out under MATLAB with no toolbox providing it.
- `medianan(x, round(n/2))` (used in `prepinv.m`'s per-window averaging with the default `avpercent=100`) always covers the full window, so it's exactly a plain NaN-mean, not a trimmed statistic, for that default configuration — cost me some time as a porter reading "median with an averaging count" as something more selective. A one-line comment at the call site might save the next person the same detour.

Thanks again for making this available — very useful software.

---

# Notes for Peter (not part of any draft)

- Both fix branches are pushed to your fork (botheredbybees/LDEO_IX) but **no PR is open yet** — nothing public/visible to Thurnherr until you say go.
- I did not touch loadrdi.m's fix in a way that affects our own Octave image (`LDEO_IX_Octave/ldeo_ix/`) — that's still the unmodified upstream behavior, matching what CHANGES.md documents ("our port deliberately replicates the buggy behavior... to remain bit-compatible"). If PR #2 gets merged upstream, worth deciding separately whether to pull the fix into our own vendored copy too, or stay pinned to the buggy-but-bit-compatible behavior.
- The licensing issue draft has a placeholder "Andreas (or whoever's picking this up)" greeting — you may want to check if Thurnherr has a preferred name/tone, or just drop the greeting.
- I did not action items 5 or 6 from the change-request doc as separate PRs since they're now folded into PR #1 above (same content, renamed per that doc's own numbering).
