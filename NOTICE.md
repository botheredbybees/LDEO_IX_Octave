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

Everything **outside** `ldeo_ix/` and `stubs/` in this repository (the
Dockerfile, build scripts, and documentation) is original packaging work
and is licensed under the MIT License — see `LICENSE`.

`stubs/` contains small, original no-op replacement functions written for
this project to allow headless execution (see `CHANGES.md`); they are
licensed under the same MIT terms.
