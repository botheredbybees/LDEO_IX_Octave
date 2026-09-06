# Handover — 2026-07-18 session

## TL;DR

Built and shipped the first slice of a planned web interface for this repo:
a FastAPI form (`webapp/`) that generates `set_cast_params.m` for a whole
cruise, replacing hand-editing. 16 tasks, 53 backend tests, pushed to
`master` at https://github.com/botheredbybees/LDEO_IX_Octave. Repo has no
CI — verification was manual (pytest + a real `docker build`/`docker run`
end-to-end pass against a mock P16N-style cruise).

## What shipped this session

- **Design spec:** `docs/superpowers/specs/2026-07-15-cruise-cast-intake-form-design.md`
- **Implementation plan:** `docs/superpowers/plans/2026-07-17-cruise-cast-intake-form.md`
  (14 tasks — read this for the exact module-by-module design and the
  Global Constraints that bind the whole slice, e.g. "every file-browse/read
  operation must resolve the requested path and assert it stays under its
  mount root before touching disk")
- **Code:** `webapp/` — mount-scoped file browsing (`file_browser.py`,
  `paths.py`), CTD/nav structural sniffing + preview (`delimited_parser.py`),
  LADCP raw-file down/up pairing (`ladcp_scan.py`), prior-cast netCDF
  attribute cloning (`netcdf_reader.py`), cast/session models + JSON sidecar
  persistence (`models.py`, `session_store.py`), the M-code generator
  (`template_gen.py`), validation (`validation.py`), the CRUD + generate API
  (`api.py`, mounted in `main.py`), and a server-rendered Jinja2 + vanilla-JS
  UI (`templates/`, `static/app.js`) — no Node/build toolchain.
- **Docker:** default entrypoint changed from `octave-cli` to the web
  server (port 8080); `octave-cli` still reachable via
  `docker run ldeo-ix-octave octave-cli`. New mounts: `/ladcp_data`,
  `/ctd_data`, `/sadcp_data`, `/navigation_data` (all optional, alongside
  the existing required `/data`).
- **Docs:** `README.md` Usage section rewritten for both workflows, plus a
  no-auth operator warning. `CLAUDE.md` repo layout table and working
  conventions updated for `webapp/`.

Executed via `superpowers:subagent-driven-development` — a fresh
implementer + reviewer subagent pair per task, with real fix-and-re-review
cycles (not rubber-stamped). Progress ledger with full detail on every task
and every fix round: `.superpowers/sdd/progress.md` (git-ignored scratch,
local only — not pushed).

## Real bugs caught and fixed along the way

Worth knowing about since some are the kind of thing that could resurface
if this code is refactored carelessly:

1. **Path-traversal oracle in validation** — `validate_session`'s
   file-existence check originally bypassed `paths.resolve_within()`
   entirely (`webapp/validation.py`). Any file-touching code path in this
   codebase MUST go through `resolve_within`; this is a hard project
   constraint, not a suggestion.
2. **Stored + reflected XSS in `app.js`** — the cast table and CTD/nav
   preview renderer originally built HTML via `innerHTML` template-literal
   interpolation of untrusted data. Fixed to `createElement`/`textContent`.
   If you add new dynamic rendering to `app.js`, follow that pattern, not
   `innerHTML`.
3. **Client-controlled `id`** — request bodies could set `CastEntry.id`
   directly, letting two casts collide and making `delete`/`update` target
   the wrong record. Fixed by stripping `id` at every construction site.
4. **NetCDF float32 precision loss** — `scipy.io.netcdf_file` writes plain
   Python floats as single-precision by default; naive `float()` widening
   is lossy. Fixed by round-tripping through `str()` first
   (`netcdf_reader.py`).
5. **Backup timestamp collision (data loss)** — the generate endpoint's
   backup-before-overwrite used a timestamp for uniqueness. Second-resolution
   collided; a "fix" to microsecond resolution *also* collided, because
   `datetime.now()` on this dev machine has real clock resolution of ~15ms
   despite printing 6 microsecond digits (empirically confirmed: 1-in-5
   real test runs failed). Final fix uses an atomic `Path.open("x", ...)`
   exclusive-create with a collision-retry loop — correct by construction,
   not by clock precision. **If you ever touch this logic again, don't
   trust `datetime.now()` uniqueness on Windows — verify empirically.**
6. **`None` rendered as literal Octave text** — `template_gen.py` emitted
   `f.ctd_header_lines = None;` for any cast that passed validation but
   left an optional field unset (every test fixture had set every field,
   so this hid until the final whole-branch review). Fixed: `add()` now
   skips emitting a line entirely when the value is `None`.
7. **`cruise_id` had no write path** — displayed in the UI, never actually
   persisted anywhere. Added `PUT /api/session`.

## Known gaps / backlog (not blocking, not fixed)

- **UI file pickers are plain text inputs, not a directory browser.** The
  backend has fully working `/api/browse/{mount}` and `/api/mounts`
  endpoints, but nothing in `app.js` calls them — the design spec described
  a "browse and pick" workflow, the shipped plan simplified this to
  type-a-relative-path + a "Preview / map columns" button. This was a
  scope decision made while writing the plan, not an oversight, but it's a
  real reduction from the original design intent. **Worth a conversation
  with the user about whether to build the tree-browser UI as a follow-up.**
- Session read-modify-write in `api.py`'s CRUD routes isn't atomic —
  concurrent requests could race (low risk under the single-operator usage
  model this tool assumes).
- `session_store.load_session()` has no error handling for a corrupt/partial
  `.cruise_intake_session.json` — would 500 with no recovery path.
- `time_start`/`time_end` list elements aren't individually type-validated;
  a stray non-numeric entry could still produce invalid Octave.
- No symlink-escape test for `paths.py` (skipped — hard to write portably
  on Windows, this project's dev platform; the `.resolve()` defense is
  still in place, just untested).
- `clone-from-netcdf` won't prefill `cast_name` — the netCDF attribute is
  named `name`, the model field is `cast_name`; the prefill only matches
  identical names.
- Unused `Any` import in `netcdf_reader.py`.
- **GitHub's license badge shows "Other", not "MIT"** — deliberate:
  `LICENSE`'s trailing note scoping it to packaging-only (excluding
  `ldeo_ix/`, per `NOTICE.md`) breaks GitHub's fuzzy license-text matcher.
  Don't "fix" this by removing the scope note — that would misrepresent
  `ldeo_ix/`'s actual (nonexistent) license status. Leave as-is.
- Areas 2–4 of the original web-interface roadmap are still just design
  notes, not built: documentation browser (see memory —
  should generate pages from the sister project's PDFs/notes for 3
  audiences, not just serve raw PDFs), output viewer, global-defaults
  editor, and eventually run orchestration (the web UI actually invoking
  `process_cast`).

## Repo/deployment state

- Pushed to `https://github.com/botheredbybees/LDEO_IX_Octave` (`master`
  branch, description set). No CI configured.
- No authentication anywhere in the web app — documented in `README.md`
  with an explicit operator warning (bind to localhost / don't publish the
  port on an untrusted network).
- `CLAUDE.md`'s opening "Repository status" section still describes this
  repo as "small, mostly done, not an active development codebase" from
  before this session — that framing is now stale given `webapp/` exists.
  Worth a touch-up next session (not done now, out of scope for this
  handover).

## How to pick this back up

```bash
# backend tests
python -m pip install -r webapp/requirements-dev.txt
python -m pytest webapp/tests -v          # expect 53 passed

# full end-to-end (Docker)
docker build -t ldeo-ix-octave:local .
docker run --rm -p 8080:8080 \
  -v "$(pwd)/my_cruise:/data" \
  -v "$(pwd)/my_cruise/raw:/ladcp_data" \
  -v "$(pwd)/my_cruise/ctd:/ctd_data" \
  -v "$(pwd)/my_cruise/sadcp:/sadcp_data" \
  -v "$(pwd)/my_cruise/nav:/navigation_data" \
  ldeo-ix-octave:local
# then open http://localhost:8080/
```

For the next slice: brainstorm area 2 (documentation browser) or the UI
file-browser backlog item above, whichever the user prioritizes. Use
`superpowers:brainstorming` → `superpowers:writing-plans` →
`superpowers:subagent-driven-development`, same as this session, following
the model-tiering preference already saved in memory (haiku for mechanical
tasks, sonnet for integration, opus for final review).

---

# Handover — 2026-09-06 session (real Nuyina LADCP cast + fix wave)

## TL;DR

A prior plan this same day drove the webapp end-to-end against a real RSV
*Nuyina* LADCP cast (station/cast 005, voyage 202324050) for the first time
and found 4 real integration gaps, initially deferred as "future work." A
whole-branch review argued these were too dangerous to leave deferred (one
had already caused a real 11-minute stuck process during that same day's
work), and this session fixed all 4, verified every fix against the exact
real scenario that failed, and committed to `master`.

## The correct `process_cast` invocation — read this before running anything

```octave
process_cast(3)              % process station/cast 3, all 17 steps
process_cast(3, 1, 0)        % same, explicit: stop=0 means "don't pause"
```

**Never pass `stop=2`.** `process_cast.m`'s own docstring comment ("2 stop
after all steps") is misleading — the real behavior, in
`ldeo_ix/end_processing_step.m`, is that `pcs.stop` is re-checked after
*every* step; `stop==1` self-resets to 0 after firing once, but `stop==2`
never resets, so it pauses after every one of the 17 steps, forever,
waiting on an interactive `return`. In a non-interactive `docker run/exec
--eval` (no stdin attached), this is an infinite `keyboard()` busy-loop, not
computation — confirmed for real: an `octave-cli` process pinned at 99% CPU
for 11+ minutes, writing a 205 MB diary log of repeated `keyboard>` prompts,
before being killed. `stop=0` (the actual coded default) is correct for an
uninterrupted, non-interactive run.

## The 4 fixes made this session

1. **README + plan/spec docs corrected** — both `process_cast(3, 1, 2)`
   examples in `README.md`, and the `process_cast(5, 1, 2)` verification
   steps in the 2026-09-06 plan/spec docs, changed to `stop=0` with an
   explanatory note (see above).

2. **`webapp/template_gen.py`: `f.ladcpdo`/`f.ladcpup`/`f.nav` now
   mount-absolute.** The webapp used to write these as bare filenames
   (e.g. `'2324050_005_down_ladcp.000'`), matching its own raw-file-scan
   convention — but `ldeo_ix/loadrdi.m`/`loadnav.m` resolve them via plain
   `exist(filename,'file')`, which only searches the `/data` working
   directory and Octave's path, neither of which is `/ladcp_data` or
   `/navigation_data`. The LADCP case fails loudly (`can not find ADCP data
   file`); the nav case fails **silently**, falling back to
   `d.slon=NaN*d.time_jul; d.slat=d.slon;` and continuing — a complete,
   plausible-looking, silently-wrong run. Fixed via a new `_mount_quote()`
   helper that joins the filename onto `config.MOUNTS["ladcp"]` /
   `config.MOUNTS["nav"]` before quoting. `f.ctd`/`f.sadcp` were already
   fine (they're the webapp's own conversion outputs, written under
   `/data`) and are untouched.

3. **`ldeo_ix/loadnav.m`: dead `f.IGRF` argument removed** (genuine upstream
   bug, documented in `CHANGES.md` per this repo's own convention). The
   `magdec`-not-found fallback branch referenced `f.IGRF` in a `sprintf`
   call — never assigned anywhere, and the format string had no `%s` for it
   anyway (always dead). This crashed Octave (`error: structure has no
   member 'IGRF'`) before ever reaching the actually-working fallback line,
   `p.drot = magdev(...)`. Any cast whose `set_cast_params.m` doesn't
   already set a finite `p.drot` hits this, and this Docker image ships no
   `magdec` binary, so every webapp-generated cast that leaves `p.drot`
   blank hits it. Fix is behavior-preserving (removed a never-used
   argument). Verified: re-running the real cast without any `eval_expr`
   workaround now computes a real declination via `magdev()` itself
   (15.057°, matching the 15.051° computed by hand in the earlier
   workaround) and proceeds cleanly.

4. **`webapp/api.py`: `/api/generate` now pre-creates `f.res`'s and
   `f.checkpoints`'s parent directories.** `process_cast.m` opens a diary
   log at `[f.res,'.log']` and later saves checkpoints under
   `f.checkpoints`, but never creates either parent directory itself — so
   the very first `process_cast` run against any webapp-generated config
   failed immediately on `diary: can't open diary file`. Fixed with a
   `mkdir(parents=True, exist_ok=True)` for both, added to the `/generate`
   route.

## Real end-to-end re-verification (this session, not the prior one)

Rebuilt the image (`docker build -t ldeo-ix-octave:local -f Dockerfile .`),
started a fresh container against the same 5 real mounts used earlier that
day (`nuyina_data/202324050_005/{data,ctd,nav,codas}` +
`nuyina_dev_env/voyage_data/sample/adcp/ladcp`), removed the prior task's
symlink workaround entirely, and re-drove the webapp API from scratch:
create cast → `/api/generate`. The freshly generated `set_cast_params.m`
now reads:

```matlab
f.ladcpdo = '/ladcp_data/2324050_005_down_ladcp.000';
f.ladcpup = '/ladcp_data/2324050_005_up_ladcp.000';
f.nav = '/navigation_data/202324050_005.navtable';
```

`/api/generate` also auto-created empty `V7/` and `checkpoints/`
directories with no manual `mkdir` step. Then ran
`process_cast(5,1,0)` directly (no symlinks, no `eval_expr` override) — real
exit, all 17 steps completed, no `error:` anywhere in the log, "whole task
took 137 seconds". Step 3 (LOAD GPS DATA) loaded the nav file straight from
`/navigation_data/...` and computed its own declination
(`p.drot = 15.057`) without crashing.

## The real scientific result (cast 005, station 5, voyage 202324050)

A real, physically plausible current profile came out of this cast, first
achieved (via workarounds) earlier the same day and reproduced cleanly this
session with the fixes in place:

- 102 depth bins, ~10 m to ~1020 m, ~10 m vertical resolution.
- `u` in `[-0.071990, 0.166196]` m/s, `v` in `[-0.087944, 0.265295]` m/s —
  well inside the plausible-ocean-current envelope, consistent with a
  shelf/slope station off south-east Tasmania (real position
  -42.559°S 148.491°E). (These are the real fixed-pipeline numbers,
  re-verified directly against the on-disk `.mat` file for this correction —
  a previous draft of this section quoted the earlier, superseded workaround
  run's numbers instead; see `task-5-report.md` for the re-derivation.)
- No NaN, not all-zero — a genuine computed solution throughout.
- The inverse solution correlates with the independently-computed shear
  solution: recomputed directly against this run's real `.mat` file,
  `corr(dr.u, dr.u_shear_method)` = **0.83** over the full profile (**0.97**
  restricted to the upper 650 m); `corr(dr.v, dr.v_shear_method)` = **0.98**
  (both scopes). The previously-stated "r=0.81" was computed against the
  now-superseded workaround run, and no command/method for it was ever
  recorded, so it isn't a verified reproduction — treat the numbers above as
  the current, real evidence of resolved current structure in the upper
  water column, not an inversion artifact.
- **Read the upper ~650 m as trustworthy current structure.** The deep
  ~370 m (652–1020 m, from the downlooker's own extended range bins, not a
  CTD extrapolation) is **noise-limited**: only ~4 velocity observations
  per bin there (vs. 5–43 shallower), and the reported velocities
  (0.016–0.021 m/s) are roughly 3x smaller than their own error bars —
  statistically indistinguishable from zero. This is because the seabed-
  detection step failed for this cast (returned an implausible 283 m depth,
  shallower than the package's own 652 m profile depth, so LDEO_IX rejected
  it and ran with no bottom-track constraint), and no SADCP data actually
  overlapped this cast's time window either. Don't cite specific deep-bin
  velocity values as measured currents; the shallow result is solid.
- **Why the workaround run and the real fixed run gave visibly different
  `u`/`v` ranges (task 3: `u=[-0.137, 0.172]`; task 4/here: `u=[-0.072,
  0.166]`) — investigated for real, not just declination rounding.** A
  controlled experiment (see `task-5-report.md`) isolated the cause: it's
  *when* the magnetic-declination rotation is applied, not the ~0.006°
  difference in the declination value itself. Supplying `p.drot` via
  `eval_expr` (the workaround's method) makes it finite before step 1, so
  `loadrdi.m` rotates the LADCP velocities immediately and `loadnav.m`'s own
  step-3 rotation is skipped; leaving `p.drot` unset (the real fixed
  pipeline) rotates once, later, in step 3 instead. Both apply exactly one
  correct rotation, but a bottom-track QC threshold in step 4 sits close
  enough to its cutoff to flip by one profile depending on that timing
  (confirmed: "removed 41" vs "removed 40" bottom-track profiles), which
  cascades through the super-ensemble/inversion steps into a materially
  different final solution. Net: `process_cast`'s `eval_expr`-supplied
  `p.drot` is not numerically equivalent to letting the pipeline compute the
  same value itself — a real gotcha for anyone using that override on
  another cast.
- **Which of the two numbers above is the "real" one is not actually
  ambiguous — Andreas Thurnherr's own official user manual settles it.**
  Per [`LDEO_IX.pdf`](https://www.ldeo.columbia.edu/~ant/UserManuals/LDEO_IX.pdf)
  (Version IX.14, the exact version this repo packages), p.10: "Once GPS
  time-series data are included in processing it is important that the
  magnetic declination (`p.drot`, or `p.poss` and `p.pose`) are **not set
  manually**... the magnetic declination is calculated before the GPS data
  are loaded!" The manual's manual-`p.drot`/`magdev()` guidance (p.3-4) is
  explicitly framed as a first-pass shortcut for when no real GPS stream
  exists yet: "for final processing it is always preferable to use a GPS
  data stream... which obviates the need to set p.poss, p.pose or p.drot."
  Cast 005 has real GPS navigation (the 86,178 real GNGGA fixes) — so per
  Andreas's own documented convention, the task-4 real fixed-pipeline run
  (`u=[-0.072, 0.166]`, `p.drot` left to compute automatically) is the one
  that follows correct practice, not task 3's `eval_expr`-supplied
  workaround. Treat `u=[-0.072, 0.166]` as the result, not "one of two
  equally valid numbers." (`examples/set_cast_params_P16N_example.m`'s own
  hardcoded `p.drot` looked like a counter-example at first glance, but that
  cast's `f.nav` is set to the same file as its `f.ctd` — a plausible sign
  it never had genuine independent GPS fixes, i.e. not actually a
  counter-example to the manual's GPS-data rule.)

## Where the full detail lives (not pushed, local only)

`.superpowers/sdd/2026-09-06-nuyina-ladcp-cast-processing/` (gitignored):
`task-1-report.md` (staging the real data), `task-2-report.md` (driving the
webapp API), `task-3-report.md` (the first, workaround-laden real run —
full diagnostic numbers, every warning, the physical-plausibility
assessment in full), `task-4-report.md` (this session's fix wave — exact
commands and output for every fix's live re-verification), `task-5-report.md`
(a later re-review's correction of this section's numbers, the recomputed
inverse/shear correlation, and the controlled experiment that root-caused
the workaround-vs-real-run `u`/`v` discrepancy). If you need the full raw
diagnostic output (LADCP QC counts, bottom-track stats, the
`GETINV`/`CHECKINV` numbers), it's all there — this handover only carries
the summary since those files don't survive outside this one clone.
