# Third-party code notice

`ldeo_ix/` is the **LDEO_IX** LADCP (Lowered Acoustic Doppler Current
Profiler) processing software:

- Original author: M. Visbeck, LDEO/Columbia University, 2003
  (http://www.ldeo.columbia.edu/ladcp)
- Later maintenance: Gerd Krahmann (IFM-GEOMAR), Frederic Marin (IRD/LEGOS),
  Jacques Grelet (IRD)

**License status:** the upstream distribution does not include a LICENSE
file or an explicit redistribution grant. Its `readme.txt` states only:

> This software is NOT A COMMERCIAL package. It is provided to you at no
> cost, but also without any guarantees for correct results.

This repository packages that code, with the minimal Octave-compatibility
patches listed in `CHANGES.md`, into a Docker image for reproducible,
headless (no-display) processing. No claim of ownership or copyright is
made over `ldeo_ix/`'s contents — copyright remains with the original
authors. If you are one of the authors and object to this distribution, or
can point to an authoritative license, please open an issue and it will be
addressed promptly.

`webapp/sadcp_convert.py` is a Python port of `ldeo_ix/mkSADCP.m` (see
above) and of the day-number formula in `ldeo_ix/julian.m`. Its logic
carries the same no-formal-license status as `ldeo_ix/` itself; only
its expression as a new, independent Python module is covered by this
project's own MIT license below.

Everything **outside** `ldeo_ix/` and `stubs/` in this repository (the
Dockerfile, build scripts, and documentation), with the exception of
`webapp/sadcp_convert.py`'s ported logic noted above, is original
packaging work and is licensed under the MIT License — see `LICENSE`.

`stubs/` contains small, original no-op replacement functions written for
this project to allow headless execution (see `CHANGES.md`); they are
licensed under the same MIT terms.

## Third-party Python dependencies

The image includes two categories of third-party Python dependencies, both
installed via pip and not vendored:

### Quick-convert (CTD processing)

The webapp's "Quick-convert (unvalidated)" CTD fallback (see
`webapp/quick_convert.py`) uses:

- [`ctdam`](https://github.com/DAM-CTD-Software/ctdam) — GPLv3. Used as
  a normal Python dependency (installed via pip, not modified or
  vendored), not redistributed as part of this project's own source.
- [`seabirdscientific`](https://github.com/Sea-BirdScientific/seabirdscientific) —
  MIT. Sea-Bird Scientific's own official community toolkit; `ctdam`
  depends on it for the actual hex-decoding/calibration math. Pulled in
  transitively via `ctdam`, not a direct dependency of this repo.

### Magnetic declination (`magdec` tool)

The `magdec` command-line tool (see `magdec/magdec.py`) uses:

- [`ppigrf`](https://github.com/iaga-vmod/ppigrf) — MIT. The Python
  port of the IGRF-14 (International Geomagnetic Reference Field)
  magnetic model, maintained by IAGA-VMOD. Provides the actual
  magnetic-declination calculations that `loadnav.m` expects from the
  `magdec` tool.
