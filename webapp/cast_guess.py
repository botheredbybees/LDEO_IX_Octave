from pathlib import Path

from webapp import config, delimited_parser, ladcp_scan, paths
from webapp.models import CastEntry

_FIELD_MAP_FIELDS = {
    "ctd": [
        "ctd_header_lines",
        "ctd_fields_per_line",
        "ctd_time_field",
        "ctd_pressure_field",
        "ctd_temperature_field",
        "ctd_salinity_field",
        "ctd_badvals",
        "ctd_time_base",
    ],
    "nav": [
        "nav_header_lines",
        "nav_fields_per_line",
        "nav_time_field",
        "nav_lat_field",
        "nav_lon_field",
        "nav_time_base",
        "nav_error",
    ],
}


def guess_next_cast(previous: CastEntry) -> dict:
    """Best-effort guess of the next cast's file locations and field
    mapping, based on the previous cast -- e.g. "004DL000.000" after
    "003DL000.000". Every file guess is verified against the real
    mounted filesystem (and, for CTD/Nav, a fresh column-count check)
    before being offered; nothing here is ever assumed.

    Returns a dict of CastEntry field overrides. Any field this
    couldn't confirm is simply absent, so the caller applies these as
    pure defaults on top of an otherwise-blank cast.
    """
    guess: dict = {}
    if previous.ladcp_station is None or not previous.ladcpdo:
        return guess

    old_token = ladcp_scan.station_token_from_filename(Path(previous.ladcpdo).name)
    if old_token is None:
        return guess

    next_station = previous.ladcp_station + 1
    new_token = str(next_station).zfill(len(old_token))

    guess["ladcp_station"] = next_station
    guess["ladcp_cast"] = previous.ladcp_cast
    guess["cast_name"] = new_token

    ladcp_mount = config.MOUNTS.get("ladcp")
    if ladcp_mount is not None and ladcp_mount.is_dir():
        for entry in ladcp_scan.scan_ladcp_directory(ladcp_mount):
            if entry.station == new_token:
                if entry.down:
                    guess["ladcpdo"] = entry.down
                if entry.up:
                    guess["ladcpup"] = entry.up
                break

    _guess_mount_file(guess, previous, "ctd", old_token, new_token)
    _guess_mount_file(guess, previous, "nav", old_token, new_token)

    return guess


def _guess_mount_file(
    guess: dict, previous: CastEntry, prefix: str, old_token: str, new_token: str
) -> None:
    previous_path = getattr(previous, prefix)
    if not previous_path or previous_path.count(old_token) != 1:
        return
    candidate = previous_path.replace(old_token, new_token)

    mount = config.MOUNTS.get(prefix)
    if mount is None:
        return
    try:
        resolved = paths.resolve_within(mount, candidate)
    except paths.PathOutsideMountError:
        return
    if not resolved.is_file():
        return

    guess[prefix] = candidate

    previous_fields_per_line = getattr(previous, f"{prefix}_fields_per_line")
    if previous_fields_per_line is None:
        return
    preview = delimited_parser.sniff_and_preview(resolved)
    if preview.fields_per_line != previous_fields_per_line:
        return

    for field in _FIELD_MAP_FIELDS[prefix]:
        value = getattr(previous, field)
        if value is not None:
            guess[field] = value
