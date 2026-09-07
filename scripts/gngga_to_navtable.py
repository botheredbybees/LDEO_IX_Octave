#!/usr/bin/env python3
"""Convert a Kongsberg GNGGA proc/csv extract (comma-delimited, ISO-8601
timestamp) into the plain whitespace-delimited, all-numeric table
ldeo_ix/loadnav.m's fscanf-based reader (and the LDEO_IX_Octave webapp's
generic column-mapper, which shares the same whitespace/all-numeric
assumption) require: elapsed_seconds lat_decimal_degrees lon_decimal_degrees,
one row per fix, no header.

elapsed_seconds is relative to --cast-start, which must be set to the exact
same value used for the cast's time_start field in the cast-config.json /
set_cast_params.m -- loadctd.m and loadnav.m both convert their own
elapsed-seconds columns to an absolute Julian date via `p.time_start`, so a
mismatch here would put the CTD and nav time series on different absolute
clocks.

This is AAD's own converter for its own Kongsberg GNGGA proc/csv export
format -- see docs/vessel-data-preparation.md for why every organization
needs its own equivalent rather than reusing this one verbatim.

--window-hours (optional, NDO-641) drops fixes more than that many hours
from --cast-start on either side. loadnav.m computes magnetic declination
from the median position of every row in the table it's given, not just
the cast's own -- an unwindowed table spanning a whole day (or two, for a
cast crossing midnight) can pull that median away from the cast's true
position for a voyage where the ship moves further between casts than
voyage 202324050 did (confirmed negligible there, not confirmed in
general). Left off by default so nothing changes for an existing caller
that doesn't pass it.
"""
import argparse
import csv
from datetime import datetime, timezone
from typing import Optional


def nmea_to_decimal(value: str, hemisphere: str) -> float:
    """Convert NMEA ddmm.mmmm (or dddmm.mmmm for longitude) to decimal degrees."""
    raw = float(value)
    degrees = int(raw / 100)
    minutes = raw - degrees * 100
    decimal = degrees + minutes / 60
    if hemisphere in ("S", "W"):
        decimal = -decimal
    return decimal


def convert(
    csv_path: str, out_path: str, cast_start: datetime, window_hours: Optional[float] = None
) -> int:
    rows_written = 0
    window_seconds = window_hours * 3600 if window_hours is not None else None
    with open(csv_path, newline="") as fh, open(out_path, "w") as out:
        reader = csv.DictReader(fh)
        for row in reader:
            timestamp = datetime.fromisoformat(row["datetime"].replace("Z", "+00:00"))
            elapsed_seconds = (timestamp - cast_start).total_seconds()
            if window_seconds is not None and abs(elapsed_seconds) > window_seconds:
                continue
            lat = nmea_to_decimal(row["latitude_dgps_gga"], row["n_or_s_dgps_gga"])
            lon = nmea_to_decimal(row["longitude_dgps_gga"], row["e_or_w_dgps_gga"])
            out.write(f"{elapsed_seconds:.3f} {lat:.6f} {lon:.6f}\n")
            rows_written += 1
    return rows_written


def _parse_cast_start(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", help="input GNGGA proc/csv extract")
    parser.add_argument("out_path", help="output plain-numeric nav table")
    parser.add_argument(
        "--cast-start",
        required=True,
        type=_parse_cast_start,
        help="cast start time, ISO-8601 (e.g. 2024-06-17T03:43:15Z) -- must match this "
             "cast's time_start in cast-config.json exactly",
    )
    parser.add_argument(
        "--window-hours",
        type=float,
        default=None,
        help="only include fixes within this many hours of --cast-start on either side "
             "(default: no windowing, include every row in the input file)",
    )
    args = parser.parse_args(argv)
    count = convert(args.csv_path, args.out_path, args.cast_start, window_hours=args.window_hours)
    print(f"wrote {count} rows to {args.out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
