#!/usr/bin/env python3
"""Convert a Kongsberg GNGGA proc/csv extract (comma-delimited, ISO-8601
timestamp) into the plain whitespace-delimited, all-numeric table
ldeo_ix/loadnav.m's fscanf-based reader (and the LDEO_IX_Octave webapp's
generic column-mapper, which shares the same whitespace/all-numeric
assumption) require: elapsed_seconds lat_decimal_degrees lon_decimal_degrees,
one row per fix, no header.

elapsed_seconds is relative to CAST_START, which must be set to the exact
same value used for the cast's time_start field in set_cast_params.m --
loadctd.m and loadnav.m both convert their own elapsed-seconds columns to
an absolute Julian date via `p.time_start`, so a mismatch here would put
the CTD and nav time series on different absolute clocks.

This is a one-off, single-cast conversion script (not a generic tool) --
CAST_START is hardcoded to cast 005's real, confirmed start time rather
than parsed from a .hdr file, since generalizing that isn't needed for
processing this one cast. See
docs/superpowers/specs/2026-09-06-nuyina-ladcp-cast-processing-design.md
for why this script exists at all.
"""
import csv
import sys
from datetime import datetime, timezone

CAST_START = datetime(2024, 6, 17, 3, 43, 15, tzinfo=timezone.utc)


def nmea_to_decimal(value: str, hemisphere: str) -> float:
    """Convert NMEA ddmm.mmmm (or dddmm.mmmm for longitude) to decimal degrees."""
    raw = float(value)
    degrees = int(raw / 100)
    minutes = raw - degrees * 100
    decimal = degrees + minutes / 60
    if hemisphere in ("S", "W"):
        decimal = -decimal
    return decimal


def convert(csv_path: str, out_path: str) -> int:
    rows_written = 0
    with open(csv_path, newline="") as fh, open(out_path, "w") as out:
        reader = csv.DictReader(fh)
        for row in reader:
            timestamp = datetime.fromisoformat(row["datetime"].replace("Z", "+00:00"))
            elapsed_seconds = (timestamp - CAST_START).total_seconds()
            lat = nmea_to_decimal(row["latitude_dgps_gga"], row["n_or_s_dgps_gga"])
            lon = nmea_to_decimal(row["longitude_dgps_gga"], row["e_or_w_dgps_gga"])
            out.write(f"{elapsed_seconds:.3f} {lat:.6f} {lon:.6f}\n")
            rows_written += 1
    return rows_written


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <input GNGGA csv> <output nav table>", file=sys.stderr)
        sys.exit(1)
    count = convert(sys.argv[1], sys.argv[2])
    print(f"wrote {count} rows to {sys.argv[2]}")
