from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import netcdf_file


def read_global_attributes(nc_path: Path) -> dict:
    if not Path(nc_path).is_file():
        raise FileNotFoundError(str(nc_path))

    attrs: dict = {}
    with netcdf_file(str(nc_path), "r", mmap=False) as nc:
        # scipy's netcdf_file has no public "list global attributes" API;
        # it stores them in this internal dict (documented workaround used
        # widely since scipy doesn't expose a first-class accessor for it).
        for name, value in nc._attributes.items():
            if isinstance(value, bytes):
                value = value.decode("utf-8", errors="replace")
            elif isinstance(value, np.floating):
                # scipy.io.netcdf_file writes plain Python floats as
                # single-precision (NC_FLOAT / numpy.float32) by default.
                # Naively widening that float32 via Python's float() does
                # NOT recover the originally-written decimal value (e.g.
                # float(np.float32(-15.498335)) == -15.498334884643555).
                # Round-tripping through str() first recovers the shortest
                # decimal that maps back to the exact float32 bit pattern,
                # which is the value that was actually written. This is
                # safe for float64 attributes too, since they're already
                # full precision and str() round-trips them exactly.
                value = float(str(value))
            attrs[name] = value
    return attrs
