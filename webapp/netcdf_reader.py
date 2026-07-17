from pathlib import Path
from typing import Any

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
            attrs[name] = value
    return attrs
