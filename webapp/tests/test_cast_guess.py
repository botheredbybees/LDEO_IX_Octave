from webapp import cast_guess, config
from webapp.models import CastEntry


def _previous_cast(**overrides) -> CastEntry:
    defaults = dict(
        ladcp_station=3,
        ladcp_cast=1,
        cast_name="003",
        ladcpdo="003DL000.000",
        ladcpup="003UL000.000",
        ctd="003.2Hz",
        ctd_header_lines=0,
        ctd_fields_per_line=4,
        ctd_time_field=1,
        ctd_pressure_field=2,
        ctd_temperature_field=3,
        ctd_salinity_field=4,
        ctd_badvals=-999,
        ctd_time_base=0,
        nav="003.2Hz",
        nav_header_lines=0,
        nav_fields_per_line=4,
        nav_time_field=1,
        nav_lat_field=2,
        nav_lon_field=3,
        nav_time_base=0,
        nav_error=30,
    )
    defaults.update(overrides)
    return CastEntry(**defaults)


def _write_4_field_file(path, contents="1.0 2.0 3.0 4.0\n5.0 6.0 7.0 8.0\n"):
    path.write_text(contents)


def test_guesses_next_station_and_finds_ladcp_pair(tmp_path, monkeypatch):
    ladcp_mount = tmp_path / "ladcp"
    ladcp_mount.mkdir()
    (ladcp_mount / "004DL000.000").write_text("")
    (ladcp_mount / "004UL000.000").write_text("")
    monkeypatch.setitem(config.MOUNTS, "ladcp", ladcp_mount)
    monkeypatch.setitem(config.MOUNTS, "ctd", tmp_path / "ctd")
    monkeypatch.setitem(config.MOUNTS, "nav", tmp_path / "nav")
    (tmp_path / "ctd").mkdir()
    (tmp_path / "nav").mkdir()

    guess = cast_guess.guess_next_cast(_previous_cast())

    assert guess["ladcp_station"] == 4
    assert guess["ladcp_cast"] == 1
    assert guess["cast_name"] == "004"
    assert guess["ladcpdo"] == "004DL000.000"
    assert guess["ladcpup"] == "004UL000.000"


def test_guesses_ctd_and_nav_paths_and_carries_over_field_mapping_when_columns_match(
    tmp_path, monkeypatch
):
    ctd_mount = tmp_path / "ctd"
    ctd_mount.mkdir()
    _write_4_field_file(ctd_mount / "004.2Hz")
    monkeypatch.setitem(config.MOUNTS, "ctd", ctd_mount)
    monkeypatch.setitem(config.MOUNTS, "nav", ctd_mount)
    monkeypatch.setitem(config.MOUNTS, "ladcp", tmp_path / "ladcp")
    (tmp_path / "ladcp").mkdir()

    guess = cast_guess.guess_next_cast(_previous_cast())

    assert guess["ctd"] == "004.2Hz"
    assert guess["ctd_header_lines"] == 0
    assert guess["ctd_pressure_field"] == 2
    assert guess["ctd_temperature_field"] == 3
    assert guess["ctd_salinity_field"] == 4
    assert guess["nav"] == "004.2Hz"
    assert guess["nav_lat_field"] == 2
    assert guess["nav_lon_field"] == 3


def test_does_not_guess_ctd_path_when_it_does_not_exist(tmp_path, monkeypatch):
    ctd_mount = tmp_path / "ctd"
    ctd_mount.mkdir()
    # no 004.2Hz written
    monkeypatch.setitem(config.MOUNTS, "ctd", ctd_mount)
    monkeypatch.setitem(config.MOUNTS, "nav", ctd_mount)
    monkeypatch.setitem(config.MOUNTS, "ladcp", tmp_path / "ladcp")
    (tmp_path / "ladcp").mkdir()

    guess = cast_guess.guess_next_cast(_previous_cast())

    assert "ctd" not in guess
    assert "ctd_pressure_field" not in guess
    assert "nav" not in guess


def test_guesses_path_but_drops_field_mapping_when_column_count_differs(
    tmp_path, monkeypatch
):
    ctd_mount = tmp_path / "ctd"
    ctd_mount.mkdir()
    # 004.2Hz has 5 fields, not 4 like the previous cast's file
    _write_4_field_file(ctd_mount / "004.2Hz", "1.0 2.0 3.0 4.0 5.0\n6.0 7.0 8.0 9.0 10.0\n")
    monkeypatch.setitem(config.MOUNTS, "ctd", ctd_mount)
    monkeypatch.setitem(config.MOUNTS, "nav", ctd_mount)
    monkeypatch.setitem(config.MOUNTS, "ladcp", tmp_path / "ladcp")
    (tmp_path / "ladcp").mkdir()

    guess = cast_guess.guess_next_cast(_previous_cast())

    assert guess["ctd"] == "004.2Hz"
    assert "ctd_pressure_field" not in guess
    assert "ctd_header_lines" not in guess


def test_does_not_guess_when_station_token_is_ambiguous_in_path(tmp_path, monkeypatch):
    ctd_mount = tmp_path / "ctd"
    ctd_mount.mkdir()
    (ctd_mount / "003_003.2Hz").write_text("1.0 2.0 3.0 4.0\n")
    monkeypatch.setitem(config.MOUNTS, "ctd", ctd_mount)
    monkeypatch.setitem(config.MOUNTS, "nav", ctd_mount)
    monkeypatch.setitem(config.MOUNTS, "ladcp", tmp_path / "ladcp")
    (tmp_path / "ladcp").mkdir()

    guess = cast_guess.guess_next_cast(_previous_cast(ctd="003_003.2Hz", nav="003_003.2Hz"))

    assert "ctd" not in guess
    assert "nav" not in guess


def test_returns_empty_dict_when_previous_cast_has_no_ladcp_station():
    previous = _previous_cast(ladcp_station=None)

    assert cast_guess.guess_next_cast(previous) == {}


def test_returns_empty_dict_when_previous_ladcpdo_does_not_match_naming_convention():
    previous = _previous_cast(ladcpdo="not_a_ladcp_filename.txt")

    assert cast_guess.guess_next_cast(previous) == {}
