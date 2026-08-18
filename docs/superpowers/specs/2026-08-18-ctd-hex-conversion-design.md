# CTD raw-hex conversion — Design

Date: 2026-08-18
Status: Approved for planning

## Context

LDEO_IX expects CTD input as an already-converted, decimated ASCII time
series with known column positions — the vendored reference example
(`examples/set_cast_params_P16N_example.m`) sets `f.ctd` (and `f.nav`) to a
file like `data/CTD/2Hz/003.2Hz`, produced upstream by Sea-Bird's own SBE
Data Processing software (raw `.hex` → engineering-unit `.cnv`/ASCII).

Every real cruise now in `test_data/` — `in2021_v04_investigator`,
`202324050_nuyina`, and the raw side of `broke_west_au0603`/`au0304_kaos` —
only has raw `.hex`, not a converted product. This isn't just a gap in what
got copied to the test drives: per Peter, most RSV Nuyina voyage data has
no CTD-processing step run on it at all, so for a real slice of this tool's
actual target users, "bring your own converted CTD file" is not merely
inconvenient, it's a hard blocker with no workaround today.

Sea-Bird's own conversion software (`SBE Data Processing`, free to
download, CLI-capable via `SBEBatch.exe`) is Windows-only. This document
covers what, if anything, this project does about that gap.

## Options considered

**A — Bundle SBE Data Processing under Wine.** Technically proven (see
`pedrolpena/sbe_ctdproc` on GitHub, which drives `SBEBatch.exe` under Wine
for exactly this purpose) and would produce Sea-Bird's own calibration-
accurate output. **Rejected.** Sea-Bird is a commercial instrument vendor;
"free to download" is not the same as "licensed for redistribution in a
Docker image," and no EULA text confirming redistribution rights could be
found. This is a materially harder licensing question than `ldeo_ix`'s own
(an academic tool with no formal license, a gray area) — a commercial
vendor's EULA should be assumed to prohibit bundling until proven
otherwise, and asking permission first is out of scope for this slice.
Wine also adds real fragility to what's currently a clean, minimal image.

**B — Document pre-converted CTD as a hard prerequisite; ship nothing.**
Zero licensing exposure, zero accuracy risk, matches how CTD processing
normally works for organizations that run it as routine shipboard
practice. **Adopted as the default/primary path** — see below.

**C — A from-scratch/third-party Python reimplementation of hex→engineering-
units conversion, used as the primary conversion path.** Rejected as
*primary* for one reason: Peter confirmed the real requirement is
"calibration-accurate, safe for real science use," and no reimplementation
can honestly claim that without extensive validation against Sea-Bird's own
reference output across sensor/calibration combinations — validation work
outside this repo's actual mission. **Adopted instead as an explicit,
clearly-labeled fallback** for the no-CTD-processing-exists case B doesn't
cover — see below.

## Decision: B is the default path, C is an explicit escape hatch

The intake form's documented, expected input remains a pre-converted CTD
file (B) — this is unchanged and is not itself a code change, just
documentation to write (README/webapp copy stating the prerequisite
explicitly, since it's implicit today).

Additionally, a **"Quick-convert (unvalidated)"** feature is added for
voyages with no CTD processing at all, using
[`ctdam`](https://github.com/DAM-CTD-Software/ctdam) (PyPI, GPLv3, actively
maintained — 31 releases through 1.13.2) to parse raw `.hex`+`.XMLCON`
directly and produce a real Sea-Bird-style `.cnv` file the intake form's
existing preview/column-mapping flow can consume unchanged (`ctdam`'s
`decode_hex()` → `CTDData.to_cnv()`).

**Correction after reading `ctdam`'s actual source (not just its PyPI
listing) during planning:** `ctdam`'s conversion math is not a from-scratch
reimplementation — `decode_hex()` is built on
[`seabirdscientific`](https://github.com/Sea-BirdScientific/seabirdscientific)
(pinned `==2.7.8`), which is **Sea-Bird Scientific's own official,
MIT-licensed community toolkit**, published under their own GitHub
organization, documenting the same processing options available in their
current desktop application ("Fathom"). This is materially better
provenance than "an independent guess at the calibration math" — it's
Sea-Bird's own published conversion code, just not their flagship
production GUI tool, and not independently re-verified by us. The
"unvalidated, emergency use only" framing and all labeling requirements
below are unchanged — this still isn't the same as running actual SBE
Data Processing, and we still haven't independently confirmed byte-for-
byte agreement with it — but the risk is lower than the original framing
implied, and it's worth being accurate about that rather than
overstating the risk in the other direction.

## Architecture

**Dependency/build finding that reshaped this section during planning,
not anticipated in the options analysis above:** `ctdam` (and
`seabirdscientific`) require **Python ≥3.12**. The Dockerfile's base
image (`gnuoctave/octave:9.2.0`) is Ubuntu 22.04, whose stock
`apt-get install python3` is 3.10 — what the existing webapp (and this
dev machine) already runs. Two ways to handle that:

- Move the *entire* webapp to Python 3.12. Simpler Dockerfile, but it
  means every contributor needs 3.12 to run `python -m uvicorn
  webapp.main:app` locally at all (this repo's own documented dev-loop
  verification method, per `HANDOVER.md`) — real friction imposed on the
  whole project by one clearly-labeled fallback feature.
- **Adopted:** isolate the Python-3.12 requirement to *just* the
  conversion call, via a subprocess boundary. The core webapp
  (`webapp/requirements.txt`, unchanged) keeps running under whatever
  Python it already does. `ctdam` goes in a new,
  separate `webapp/requirements-quickconvert.txt`, installed into its
  own venv built from a `deadsnakes`-PPA Python 3.12 (Ubuntu 22.04's
  standard route to a newer Python) — see the plan for the exact
  Dockerfile changes.

**New modules:**
- `webapp/quick_convert_worker.py` — a small standalone script, run
  *only* inside the Python-3.12 venv via subprocess, never imported by
  the main app. Takes `hex_path`, `xmlcon_path`, `output_path` as CLI
  args; calls `ctdam.conv.decode_hex(hex_path, xmlcon_path)` →
  `CTDData.to_cnv(output_path)`; exits 0 on success, non-zero with a
  message on stderr otherwise. Verified against `ctdam`'s actual source
  (not just its PyPI listing): `decode_hex()`'s own docstring confirms
  it (1) reads raw `.hex`, (2) converts using calibration info from the
  `.xmlcon`, (3) fixes the time array, (4) determines cast start/end,
  (5) adds Location/Flag columns — real conversion, not a stub. A
  genuine `.cnv` file needs no special handling to preview:
  `delimited_parser.sniff_and_preview` already treats any line whose
  tokens aren't all-numeric as a header line, which is exactly how
  `.cnv`'s `#`/`*`-prefixed header and `*END*` marker read — so the
  existing CTD preview/column-mapping UI works on the result completely
  unchanged.
- `webapp/quick_convert.py` — runs in the main (3.10) process. Resolves
  the requested `hex_path`/`xmlcon_path` within the `ctd` mount (reusing
  `paths.resolve_within`), picks the output path under
  `data/quick_convert/`, invokes the worker script via `subprocess.run`
  against the dedicated venv's `python3.12` binary, and turns a non-zero
  exit into a clear error. This module's own logic (path resolution,
  output naming, subprocess invocation and error handling) is fully
  unit-testable on plain Python 3.10 by mocking `subprocess.run` — no
  Python 3.12 needed for most of this feature's own test coverage; only
  a true end-to-end pass (real `ctdam` conversion of a real `.hex` file)
  needs the actual 3.12 environment, and that's verified inside a real
  `docker build`/`docker run`, matching how this repo already verifies
  Octave-side changes.

**New endpoint:** `POST /api/quick-convert/ctd` — body: `{hex_path,
xmlcon_path}` (both `ctd`-mount-relative, resolved via the existing
`paths.resolve_within` — no new path-safety code needed, reuse what
`file_browser`/`api.py` already do). Writes its output under the **`data`
mount**, not the `ctd` mount — matching the existing `generate` endpoint's
convention (`config.MOUNTS["data"] / "set_cast_params.m"`), since `data`
is the one mount the README guarantees is writable; `ctd`/`nav`/`ladcp`/
`sadcp` may well be read-only bind mounts of raw ship data in practice,
and writing a converted file back into someone's raw-data directory would
be a bad default even where it happens to be writable. Output path:
`data/quick_convert/<hex-stem>.UNVALIDATED_QUICKCONVERT.cnv` (`.cnv`, not
`.txt` as originally drafted — it's a genuine `.cnv` file, the extension
should say so). Returns `{"ctd_path": "quick_convert/<name>"}`.

**Resolved (was an open detail above):** the CTD fieldset's `ctd-path`
input is normally `ctd`-mount-relative, but quick-convert's output lives
under `data`. Rather than add a session-level "is this quick-converted"
flag, the fixed filename suffix already required for labeling purposes
(below) doubles as the routing signal: the frontend's Preview click
handler checks whether the current `ctd-path` value ends in
`.UNVALIDATED_QUICKCONVERT.cnv` and calls `/api/preview/data?path=...`
instead of `/api/preview/ctd?path=...` when it does — no backend change
needed, `/api/preview/{mount}` is already mount-generic. The same suffix
check drives the warning banner and a small fix to
`validation.py`'s existing per-field mount-existence check (today it
always checks the `ctd` field against the `ctd` mount; a quick-converted
value needs checking against `data` instead, or it'll produce a
spurious "not found under ctd mount" warning for a file that
genuinely exists). `f.ctd` in the generated `set_cast_params.m` is
written exactly like any other value in that field today — verbatim,
with no mount translation — so this introduces no new behavior there.

**New UI:** a "Quick-convert raw hex (unvalidated, emergency use only)"
button in the CTD fieldset, next to the existing Browse/Preview controls.
Clicking it opens two file-browser panels (reusing the browser widget just
built) to pick the `.hex` and `.XMLCON` inputs, then calls the new
endpoint and, on success, fills the `ctd-path` input with the generated
file's path — same handoff point the existing Browse flow already uses, so
Preview/map-columns works on the result without any changes to that code.

**Labeling requirements (non-negotiable, not a nice-to-have):**
- The button text itself says "unvalidated, emergency use only."
- A persistent warning banner appears in the CTD fieldset whenever a
  quick-converted file is in use (detectable by the filename suffix).
- Generated output filenames get a fixed suffix,
  `<original-hex-stem>.UNVALIDATED_QUICKCONVERT.cnv`, so the provenance is
  visible in the filesystem itself, not just the UI — a file that
  outlives this browser session (gets committed to a cruise's data
  directory, gets emailed to someone) still carries the warning.
- The webapp README/docs section covering this feature states plainly:
  this exists for voyages with no CTD processing at all, is not
  Sea-Bird-equivalent, and its output should never be treated as
  publication-grade without independent verification.

**Licensing:** `ctdam` (GPLv3) added to the new
`webapp/requirements-quickconvert.txt` (not the main
`webapp/requirements.txt` — see the subprocess-isolation note above),
which transitively pulls in `seabirdscientific` (MIT, Sea-Bird Scientific's own
official toolkit — see the correction above). `NOTICE.md` gets a new
section alongside the existing `ldeo_ix`/`stubs` disclosure, documenting
both dependencies and linking their source (PyPI/GitHub) —
straightforward disclosure either way, not the same class of open
question as Option A's Sea-Bird EULA gap, since these are normal
third-party Python dependencies with clear licenses, not redistributed
vendor software of unclear status.

## Testing

- `webapp/quick_convert.py`'s own logic (path resolution, output naming,
  subprocess invocation and error handling) gets unit tests following
  the existing pattern (`webapp/tests/`, `pytest`), with `subprocess.run`
  mocked — runs on plain Python 3.10, no network/Docker/3.12 required.
- `webapp/quick_convert_worker.py`'s real conversion is verified inside
  an actual `docker build`/`docker run` pass against a real `.hex`+
  `.XMLCON` pair from `test_data/` — this is the only part of the
  feature that genuinely needs Python 3.12, so it's verified where that
  environment actually exists rather than assumed to work.
- UI wiring verified manually (Playwright against a running server), same
  pattern used for the file-browser work: exercise the button against a
  real `test_data/` cruise, confirm the warning banner and filename
  suffix both appear, confirm the resulting path feeds into the existing
  Preview flow correctly.
- No accuracy/validation test suite is in scope — that would imply a
  claim of scientific correctness this feature explicitly disclaims.

## Explicitly out of scope

- Any bundling of Sea-Bird's own software (Option A, rejected above).
- Validating `ctdam`'s conversion accuracy against Sea-Bird's official
  output. If this is ever wanted, it's a separate, much larger piece of
  work (would need reference `.hex`/`.cnv` pairs produced by real SBE
  Data Processing runs across multiple sensor/calibration configurations)
  and does not block this slice.
- Extending quick-convert to any file type other than CTD hex (e.g. no
  equivalent fallback for LADCP raw-file conversion is proposed here —
  LADCP's raw PD0 format doesn't have the same "needs vendor software to
  become usable" problem CTD hex does; LDEO_IX reads PD0 directly).
