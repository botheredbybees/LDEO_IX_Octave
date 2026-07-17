# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## What this project is

A Docker image that packages **LDEO_IX** (the LDEO/Columbia GO-SHIP LADCP
processing MATLAB software, by M. Visbeck / Gerd Krahmann / Frederic Marin /
Jacques Grelet) to run under **GNU Octave 9.2** instead of MATLAB. It's a
standalone packaging project — small, mostly done, not an active development
codebase with a roadmap. Most future sessions here will be maintenance:
Octave version bumps, new patches when a user hits an incompatibility, or
documentation fixes.

This repo was spun out of a separate project (`LADCP`, a Python LADCP
toolkit) where the patched code lived under `octave_harness/ldeo_ix/` as a
differential-testing harness. That harness also had diagnostic/comparison
scripts (Python-side stage diffing against a from-scratch reimplementation)
which were **deliberately left behind** — this repo is the clean, general-
purpose runnable image only. Don't assume that harness exists or try to
recreate it here; if the user wants that comparison tooling, it lives in the
other project.

## Repository status (as of 2026-07-15)

- Git-initialized locally, one commit, **no remote configured yet**.
- Docker image builds and has been smoke-tested locally
  (`docker build -t ldeo-ix-octave:local .`; ran `default.m` inside the
  container and confirmed it executes real LDEO_IX M-code under Octave).
- **Not yet pushed to GitHub or Docker Hub.** The user chose to prepare
  everything locally and review before publishing (this is going public, per
  the user's explicit choice — see Licensing below). Don't push either
  without the user's explicit go-ahead in that session.

## Licensing — read `NOTICE.md` before touching anything redistribution-related

This is the one thing that actually matters in this repo. `ldeo_ix/` is
third-party scientific code with **no formal upstream license** — only a
"free, no warranty" disclaimer in the original author's readme. The user
chose to make this repo/image **public** with that risk explicitly
acknowledged. Implications for future work:

- Never add a blanket LICENSE claim over `ldeo_ix/`'s contents — the MIT
  `LICENSE` file in this repo covers only the packaging (`Dockerfile`,
  `stubs/`, docs), not `ldeo_ix/`. Keep that split intact in any doc edits.
  See `NOTICE.md` for the exact wording and reasoning.
  - `stubs/` is original code (headless plotting no-ops) written for this
    project, and *is* MIT-licensed.
- If a session's task involves adding more upstream LDEO_IX files (e.g. a
  user wants a function this image doesn't have), the same "no license,
  patches documented, provenance preserved" treatment applies — extend
  `CHANGES.md`, don't silently absorb new files without a note.
- Don't relicense, don't add a CLA, don't add telemetry/attribution
  stripping. If in doubt, ask the user before publishing further.

## Repo layout

| Path | Purpose |
|---|---|
| `ldeo_ix/` | LDEO_IX source, patched to run under Octave. Every patch is listed in `CHANGES.md` — don't make undocumented changes here. |
| `stubs/` | No-op replacements for plotting functions (`figure`, `plot`, `subplot`, ...) plus two genuinely missing/incompatible functions (`makebars`, `interp1q`). Needed because the Docker image is headless. `set.m` is the one stub with real logic (no-ops only on graphics-handle calls, falls through otherwise) — don't blanket-stub `set`/`get` further; that was a deliberate constraint carried over from the original harness work. |
| `examples/set_cast_params_P16N_example.m` | A worked example of the one file every LDEO_IX cruise/cast must supply. Cast-specific (hardcoded paths, lat/lon, timestamps for one real GO-SHIP cast) — a reference, not a default config. Don't "fix" it to be generic; if you want a generic template, add a second file rather than genericizing this one (it's deliberately a real worked example). |
| `webapp/` | Web intake form (FastAPI + Jinja2 + vanilla JS) that generates `set_cast_params.m`. No Node/build toolchain. Tests live in `webapp/tests/`, run via `python -m pytest webapp/tests`. |
| `Dockerfile` | Builds `FROM docker.io/gnuoctave/octave:9.2.0`, copies `ldeo_ix/` and `stubs/` in, sets `OCTAVE_PATH` so stubs shadow real plotting builtins. |
| `CHANGES.md` | The complete, authoritative patch list against upstream LDEO_IX. Update this any time `ldeo_ix/` changes — it's the thing that makes "patched, not silently forked" true. |
| `NOTICE.md` | Provenance and license status. |
| `README.md` | User-facing usage docs (build, run, `process_cast` invocation). |

## Working conventions

- **Don't modify `ldeo_ix/` without adding an entry to `CHANGES.md`.** This
  mirrors the source project's rule about not silently diverging from
  upstream reference code — the whole point of this repo is a transparent,
  minimal patch set, not a fork.
- Verify changes by actually building and running the image, not just
  reading the Dockerfile — Octave-vs-MATLAB incompatibilities are exactly
  the kind of thing that looks fine and isn't. Pattern used last session:
  ```bash
  docker build -t ldeo-ix-octave:local .
  docker run --rm ldeo-ix-octave:local --eval "f=struct();p=struct();ps=struct();att=struct();default; disp(p.software)"
  ```
  `which('process_cast')` / `which('plot')` is a fast way to confirm
  `ldeo_ix/` vs `stubs/` path resolution without a full cast run.
- This machine is Windows; `docker build`/`docker run` work fine from Git
  Bash. Line-ending warnings (`LF will be replaced by CRLF`) on `git add`
  are normal noise from `core.autocrlf`, not a problem to fix.
- No test suite exists (there's no reference cast data shipped in this
  repo — that lived in the source project's `test_data/`, not copied here).
  "Testing" a change means building the image and running the relevant
  `process_cast` step(s) against a real or example cast directory.
- Keep `examples/` and `README.md` in sync if you change how the image is
  invoked (entrypoint, `OCTAVE_PATH`, mount point).
- `webapp/` changes should keep the pure-logic modules (`paths.py`,
  `delimited_parser.py`, `ladcp_scan.py`, `netcdf_reader.py`,
  `template_gen.py`, `validation.py`) unit-tested; UI/route wiring is
  verified manually (`python -m uvicorn webapp.main:app` + browser, or a
  full `docker build`/`docker run`) per the pattern in
  `docs/superpowers/specs/2026-07-15-cruise-cast-intake-form-design.md`.
