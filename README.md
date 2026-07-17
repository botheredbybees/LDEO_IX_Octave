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
- `Dockerfile` — builds the image from `docker.io/gnuoctave/octave:9.2.0`.

## Build

```bash
docker build -t ldeo-ix-octave .
```

## Usage

By default, `docker run ldeo-ix-octave` (with no arguments) starts a web server on port 8080 for building `set_cast_params.m`. To use the direct Octave CLI workflow below, append `octave-cli` to your docker run command.

LDEO_IX expects one `set_cast_params.m` per cast, plus the cast's raw data,
in your current working directory. `process_cast.m` loads it automatically.

1. Create a working directory with your raw LADCP/CTD/nav data and a
   `set_cast_params.m` (start from `examples/set_cast_params_P16N_example.m`
   — it documents every field). `readme` details for the *original* LDEO_IX
   directory layout are in the upstream project; this image doesn't require
   that full tree, only what your `set_cast_params.m` references.

2. Run the container with that directory mounted at `/data`:

   ```bash
   docker run --rm -it -v "$(pwd)/my_cast:/data" ldeo-ix-octave octave-cli
   ```

   This drops you into `octave-cli` with `ldeo_ix/` and `stubs/` already on
   the path.

3. Process a cast:

   ```octave
   process_cast(3)              % process station/cast 3
   process_cast(3, 1, 2)        % run all 17 steps without stopping
   ```

   See the docstring in `ldeo_ix/process_cast.m` for the full step list,
   checkpoint/resume behavior, and `begin_step`/`stop` arguments.

You can also run a script non-interactively:

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
