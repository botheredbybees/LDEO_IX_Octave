from webapp import template_gen
from webapp.models import CastEntry, CruiseSession


def _p16n_cast003():
    return CastEntry(
        cast_name="003",
        ladcp_station=3,
        ladcp_cast=1,
        ladcpdo="data/raw/003DL000.000",
        ladcpup="data/raw/003UL000.000",
        ctd="data/CTD/2Hz/003.2Hz",
        nav="data/CTD/2Hz/003.2Hz",
        ctd_header_lines=0,
        ctd_fields_per_line=11,
        ctd_time_field=1,
        ctd_pressure_field=2,
        ctd_temperature_field=3,
        ctd_salinity_field=4,
        ctd_badvals=-999,
        ctd_time_base=0,
        nav_header_lines=0,
        nav_fields_per_line=11,
        nav_time_field=1,
        nav_lat_field=10,
        nav_lon_field=11,
        nav_time_base=0,
        nav_error=30,
        drot=12.318441,
        lat=-15.498335,
        lon=-150.19699,
        time_start=[2015, 4, 11, 17, 36, 23.312975],
        time_end=[2015, 4, 11, 21, 9, 42.220459],
        btrk_mode=3,
        btrk_used=1,
        checkpoints_file="checkpoints/003",
        res_file="V7/003",
        checkpoints_steps="1:16",
    )


def test_renders_switch_case_with_one_cast_per_station():
    session = CruiseSession(cruise_id="P16N", casts=[_p16n_cast003()])

    output = template_gen.render_set_cast_params(session)

    assert "cruise_id = 'P16N';" in output
    assert "switch stn" in output
    assert "case 3" in output
    assert "f.ladcpdo = 'data/raw/003DL000.000';" in output
    assert "f.ladcpup = 'data/raw/003UL000.000';" in output
    assert "p.lat = -15.498335;" in output
    assert "p.time_start = [2015 4 11 17 36 23.312975];" in output
    assert "p.checkpoints = 1:16;" in output
    assert output.strip().endswith("end")


def test_renders_multiple_casts_as_separate_cases():
    cast3 = _p16n_cast003()
    cast4 = _p16n_cast003()
    cast4.ladcp_station = 4
    cast4.cast_name = "004"

    session = CruiseSession(cruise_id="P16N", casts=[cast3, cast4])

    output = template_gen.render_set_cast_params(session)

    assert "case 3" in output
    assert "case 4" in output


def test_omits_sadcp_line_when_unset():
    cast = _p16n_cast003()
    session = CruiseSession(casts=[cast])

    output = template_gen.render_set_cast_params(session)

    assert "f.sadcp" not in output


def test_includes_sadcp_line_when_set():
    cast = _p16n_cast003()
    cast.sadcp = "data/sadcp/003.mat"
    session = CruiseSession(casts=[cast])

    output = template_gen.render_set_cast_params(session)

    assert "f.sadcp = 'data/sadcp/003.mat';" in output


def test_quotes_are_escaped_in_string_fields():
    cast = _p16n_cast003()
    cast.cast_name = "o'brien"
    session = CruiseSession(casts=[cast])

    output = template_gen.render_set_cast_params(session)

    assert "p.name = 'o''brien';" in output
