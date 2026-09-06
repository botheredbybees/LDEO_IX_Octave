from webapp import config
from webapp.models import CastEntry, CruiseSession


def render_set_cast_params(session: CruiseSession) -> str:
    lines = [f"cruise_id = '{_escape(session.cruise_id)}';", "p.cruise_id = cruise_id;", "", "switch stn"]

    for cast in session.casts:
        lines.append(f"  case {cast.ladcp_station}")
        lines.extend(_render_cast_body(cast))
        lines.append("")

    lines.append("end")
    return "\n".join(lines) + "\n"


def _render_cast_body(cast: CastEntry) -> list:
    body = []

    def add(field, value):
        if value is None:
            return
        body.append(f"    {field} = {value};")

    add("f.ladcpdo", _mount_quote("ladcp", cast.ladcpdo))
    add("f.ladcpup", _mount_quote("ladcp", cast.ladcpup))
    add("p.ladcp_station", cast.ladcp_station)
    add("p.ladcp_cast", cast.ladcp_cast)
    add("p.name", _quote(cast.cast_name))

    add("f.ctd", _quote(cast.ctd))
    add("f.nav", _mount_quote("nav", cast.nav))
    add("f.ctd_header_lines", cast.ctd_header_lines)
    add("f.ctd_fields_per_line", cast.ctd_fields_per_line)
    add("f.ctd_time_field", cast.ctd_time_field)
    add("f.ctd_pressure_field", cast.ctd_pressure_field)
    add("f.ctd_temperature_field", cast.ctd_temperature_field)
    add("f.ctd_salinity_field", cast.ctd_salinity_field)
    add("f.ctd_badvals", cast.ctd_badvals)
    add("f.ctd_time_base", cast.ctd_time_base)
    add("f.nav_header_lines", cast.nav_header_lines)
    add("f.nav_fields_per_line", cast.nav_fields_per_line)
    add("f.nav_time_field", cast.nav_time_field)
    add("f.nav_lat_field", cast.nav_lat_field)
    add("f.nav_lon_field", cast.nav_lon_field)
    add("f.nav_time_base", cast.nav_time_base)
    add("p.nav_time_base", cast.nav_time_base)
    add("p.nav_error", cast.nav_error)

    if cast.sadcp:
        add("f.sadcp", _quote(cast.sadcp))

    add("p.drot", cast.drot)
    add("p.lat", cast.lat)
    add("p.lon", cast.lon)
    add("p.time_start", _matlab_vector(cast.time_start))
    add("p.time_end", _matlab_vector(cast.time_end))

    add("p.btrk_mode", cast.btrk_mode)
    add("p.btrk_used", cast.btrk_used)

    add("f.checkpoints", _quote(cast.checkpoints_file))
    add("f.res", _quote(cast.res_file))
    add("p.checkpoints", cast.checkpoints_steps)

    return body


def _quote(value: str) -> str:
    return "'" + (value or "").replace("'", "''") + "'"


def _mount_quote(mount_name: str, filename: str) -> str:
    # f.ladcpdo/f.ladcpup/f.nav point at raw files that live on an externally
    # mounted, read-only directory (/ladcp_data, /navigation_data), never the
    # /data working directory process_cast runs from. ldeo_ix resolves these
    # filenames via plain `exist(filename,'file')`, which only searches the
    # current working directory and Octave's path -- neither mount is on
    # either, so a bare filename never resolves. Write the mount-absolute
    # path instead. (Not needed for f.ctd/f.sadcp: those are the webapp's
    # own conversion outputs, already written as data-relative paths.)
    if not filename:
        return _quote(filename)
    return _quote(str(config.MOUNTS[mount_name] / filename))


def _escape(value: str) -> str:
    return (value or "").replace("'", "''")


def _matlab_vector(values) -> str:
    if not values:
        return "[]"
    return "[" + " ".join(str(v) for v in values) + "]"
