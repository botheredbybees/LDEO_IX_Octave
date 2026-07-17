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
        body.append(f"    {field} = {value};")

    add("f.ladcpdo", _quote(cast.ladcpdo))
    add("f.ladcpup", _quote(cast.ladcpup))
    add("p.ladcp_station", cast.ladcp_station)
    add("p.ladcp_cast", cast.ladcp_cast)
    add("p.name", _quote(cast.cast_name))

    add("f.ctd", _quote(cast.ctd))
    add("f.nav", _quote(cast.nav))
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


def _escape(value: str) -> str:
    return (value or "").replace("'", "''")


def _matlab_vector(values) -> str:
    if not values:
        return "[]"
    return "[" + " ".join(str(v) for v in values) + "]"
