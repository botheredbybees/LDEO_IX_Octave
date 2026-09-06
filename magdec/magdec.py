#!/usr/bin/env python3
"""magdec -- CLI replacement for Eric Firing's original magdec tool that
ldeo_ix/loadnav.m's geomag() subfunction shells out to. Uses ppigrf
(IGRF-14, IAGA-VMOD) instead of the original tool's own bundled model,
since every official distribution channel for the original binary is
unreachable as of 2026-09-06 (see CHANGES.md).

Two calling conventions, both dictated by ldeo_ix/loadnav.m's own logic
(NOT a general-purpose CLI design choice -- see
docs/superpowers/specs/2026-09-06-magdec-replacement-design.md):
- zero arguments: existence probe. loadnav.m's `[s,o]=system('magdec')`
  checks specifically for exit status 1 to decide whether to use this
  tool at all -- print usage, exit 1.
- five arguments (lon lat year month day): print
  "declination inclination horizontal_intensity total_intensity",
  space-separated, one line, exit 0. Only the first value (declination)
  is actually read by loadnav.m; the rest exist for output-shape parity
  with the original tool.
"""
import math
import sys
from datetime import datetime


def compute(lon: float, lat: float, year: int, month: int, day: int) -> tuple:
    import ppigrf

    # ppigrf compares its date argument against a pandas DatetimeIndex
    # internally -- a plain datetime.date raises TypeError there
    # ("Cannot compare Timestamp with datetime.date"), confirmed by
    # running this for real; datetime.datetime works.
    Be, Bn, Bu = ppigrf.igrf(lon, lat, 0.0, datetime(year, month, day))
    # ppigrf returns 1-element numpy arrays for a scalar input point,
    # not plain floats -- float() on one works today but is deprecated
    # (confirmed via -W error::DeprecationWarning), so extract with
    # .item() instead.
    Be, Bn, Bu = float(Be.item()), float(Bn.item()), float(Bu.item())

    horizontal = math.hypot(Be, Bn)
    declination = math.degrees(math.atan2(Be, Bn))
    inclination = math.degrees(math.atan2(-Bu, horizontal))
    total = math.sqrt(Be ** 2 + Bn ** 2 + Bu ** 2)
    return declination, inclination, horizontal, total


def main(argv) -> int:
    if len(argv) != 5:
        print("usage: magdec <lon> <lat> <year> <month> <day>", file=sys.stderr)
        return 1
    lon, lat = float(argv[0]), float(argv[1])
    year, month, day = int(argv[2]), int(argv[3]), int(argv[4])
    d, i, h, f = compute(lon, lat, year, month, day)
    print(f"{d:.4f} {i:.4f} {h:.1f} {f:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
