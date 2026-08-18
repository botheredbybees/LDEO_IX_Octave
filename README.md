# ldeo-ix-octave

A Docker image that runs **LDEO_IX**, the LDEO/Columbia GO-SHIP LADCP
(Lowered Acoustic Doppler Current Profiler) processing software, under
[GNU Octave](https://octave.org/) instead of MATLAB — so you can process
LADCP casts without a MATLAB license.

LDEO_IX is the reference implementation used across much of the GO-SHIP
community for turning raw Teledyne RDI Workhorse ADCP data, plus CTD/nav/
SADCP/bottom-track inputs, into full-water-column current profiles
(`process_cast.m`'s 17-step pipeline). This image runs that pipeline
unmodified except for the small compatibility patches in `CHANGES.md` and a
set of headless plotting stubs (there's no display in a container).

See `NOTICE.md` for provenance and license status of the upstream code —
**read it before redistributing this image further.**

## What's in here

- `ldeo_ix/` — LDEO_IX source, patched to run under Octave 9.2 (see
  `CHANGES.md` for every change).
- `stubs/` — no-op replacements for plotting functions (`figure`, `plot`,
  `subplot`, ...) and two genuinely missing/incompatible functions
  (`makebars`, `interp1q`), so the pipeline runs headless.
- `examples/set_cast_params_P16N_example.m` — a worked example of the one
  file every cruise/cast must supply (see below). Cast-specific — copy and
  edit it, don't run it as-is.
- `webapp/` — the web intake form (FastAPI + vanilla JS) that generates
  `set_cast_params.m`; see `docs/superpowers/specs/2026-07-15-cruise-cast-intake-form-design.md`
  for its design.
- `Dockerfile` — builds the image from `docker.io/gnuoctave/octave:9.2.0`.

## Build

```bash
docker build -t ldeo-ix-octave .
```

## Usage

### Web intake form (default)

`docker run ldeo-ix-octave` starts a web server on port 8080 for building
`set_cast_params.m` through a form instead of hand-editing it. Mount your
working directory at `/data`, plus whichever source-data directories you
have, then open the form in a browser:

```bash
docker run --rm -p 8080:8080 \
  -v "$(pwd)/my_cruise:/data" \
  -v "$(pwd)/my_cruise/raw:/ladcp_data" \
  -v "$(pwd)/my_cruise/ctd:/ctd_data" \
  -v "$(pwd)/my_cruise/sadcp:/sadcp_data" \
  -v "$(pwd)/my_cruise/nav:/navigation_data" \
  ldeo-ix-octave
```

Open `http://localhost:8080/` and add each cast — the form suggests raw
LADCP file pairs, lets you preview and column-map CTD/nav files, and can
clone a previous cast (in this session, or from a prior processed cast's
output `.nc`) as a starting point. Generating writes `/data/set_cast_params.m`
(backing up any existing file first).

**CTD input must already be converted.** The form's CTD field expects an
already-converted, decimated ASCII/`.cnv` time series (the standard
output of Sea-Bird's own SBE Data Processing software) — not a raw
`.hex` file. If your voyage's CTD data was never run through that
conversion step, see "Quick-convert" below for a fallback; for anyone
who does have Sea-Bird's software, that's still the right way to get a
science-grade converted file.

**No authentication:** the web form has no login and anyone who can reach
the port can browse the mounted directories and overwrite
`set_cast_params.m`. It's built for a single trusted operator — only
publish `-p 8080:8080` on a network you trust (e.g. bind to `127.0.0.1`
instead of all interfaces, or don't publish the port at all and use
`docker exec`/an SSH tunnel).

### Quick-convert (unvalidated)

For voyages with no CTD processing at all, the CTD fieldset has a
"Quick-convert raw hex" option that turns a raw `.hex`+`.XMLCON` pair
into a usable `.cnv` file automatically, using the open-source `ctdam`
library. **This is not Sea-Bird-equivalent and its output should never
be treated as publication-grade without independent verification** —
it exists purely so a cast with no other CTD conversion available isn't
a hard blocker. Converted files are written under `data/quick_convert/`
— the `data` mount must be writable for this feature to work, unlike
the read-only-safe default flow. Quick-converted files are always named
`<original>.UNVALIDATED_QUICKCONVERT.cnv` so the provenance travels with
the file even outside this tool.

### Direct Octave CLI

The original CLI workflow (LDEO_IX expects one `set_cast_params.m` per cast,
plus the cast's raw data, in your current working directory —
`process_cast.m` loads it automatically) is still available:

```bash
docker run --rm -it -v "$(pwd)/my_cast:/data" ldeo-ix-octave octave-cli
```

This drops you into `octave-cli` with `ldeo_ix/` and `stubs/` already on
the path. Process a cast:

```octave
process_cast(3)              % process station/cast 3
process_cast(3, 1, 2)        % run all 17 steps without stopping
```

See the docstring in `ldeo_ix/process_cast.m` for the full step list,
checkpoint/resume behavior, and `begin_step`/`stop` arguments. You can also
run a script non-interactively:

```bash
docker run --rm -v "$(pwd)/my_cast:/data" ldeo-ix-octave octave-cli --eval "process_cast(3,1,2)"
```

## Why Octave instead of MATLAB

MATLAB licensing is a real barrier for many oceanographers, especially
outside institutions with a site license. Octave is free and largely
source-compatible; the patches in `CHANGES.md` close the small remaining
gaps (a couple of reserved-keyword collisions, one missing builtin, and
headless plotting).

## License

The packaging (Dockerfile, `stubs/`, documentation) is MIT-licensed — see
`LICENSE`. `ldeo_ix/` is third-party code with no formal upstream license;
see `NOTICE.md`.
