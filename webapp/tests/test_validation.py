from webapp import config, validation
from webapp.models import CastEntry, CruiseSession


def _valid_cast(**overrides):
    defaults = dict(
        ladcpdo="003DL000.000",
        ladcpup="003UL000.000",
        ladcp_station=3,
        ladcp_cast=1,
        lat=-15.5,
        lon=-150.2,
        time_start=[2015, 4, 11, 17, 36, 23.0],
        time_end=[2015, 4, 11, 21, 9, 42.0],
    )
    defaults.update(overrides)
    return CastEntry(**defaults)


def test_valid_session_has_no_errors():
    session = CruiseSession(casts=[_valid_cast()])

    result = validation.validate_session(session)

    assert result.is_valid is True
    assert result.errors == {}


def test_missing_required_field_produces_error():
    cast = _valid_cast(lat=None)
    session = CruiseSession(casts=[cast])

    result = validation.validate_session(session)

    assert result.is_valid is False
    assert "lat is required" in result.errors[cast.id]


def test_zero_lat_and_lon_are_valid_not_missing():
    cast = _valid_cast(lat=0.0, lon=0.0, ladcp_station=0, ladcp_cast=0)
    session = CruiseSession(casts=[cast])

    result = validation.validate_session(session)

    assert result.is_valid is True
    assert cast.id not in result.errors


def test_missing_referenced_file_produces_warning_not_error(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "ladcp", tmp_path)
    cast = _valid_cast(ladcpdo="does-not-exist.000")
    session = CruiseSession(casts=[cast])

    result = validation.validate_session(session)

    assert result.is_valid is True
    assert "does-not-exist.000 not found under ladcp mount" in result.warnings[cast.id]


def test_existing_referenced_file_produces_no_warning(tmp_path, monkeypatch):
    (tmp_path / "003DL000.000").write_text("")
    (tmp_path / "003UL000.000").write_text("")
    monkeypatch.setitem(config.MOUNTS, "ladcp", tmp_path)
    cast = _valid_cast()
    session = CruiseSession(casts=[cast])

    result = validation.validate_session(session)

    assert cast.id not in result.warnings


def test_traversal_attempt_produces_generic_warning_not_a_bypass(tmp_path, monkeypatch):
    mount = tmp_path / "mount"
    mount.mkdir()
    (tmp_path / "secret.txt").write_text("outside the mount")
    monkeypatch.setitem(config.MOUNTS, "ladcp", mount)
    cast = _valid_cast(ladcpdo="../secret.txt")
    session = CruiseSession(casts=[cast])

    result = validation.validate_session(session)

    assert result.is_valid is True
    assert "../secret.txt not found under ladcp mount" in result.warnings[cast.id]


def test_quick_converted_ctd_checked_against_data_mount_not_ctd_mount(tmp_path, monkeypatch):
    data_mount = tmp_path / "data"
    ctd_mount = tmp_path / "ctd"
    ladcp_mount = tmp_path / "ladcp"
    data_mount.mkdir()
    ctd_mount.mkdir()
    ladcp_mount.mkdir()
    quick_convert_dir = data_mount / "quick_convert"
    quick_convert_dir.mkdir()
    (quick_convert_dir / "cast.UNVALIDATED_QUICKCONVERT.cnv").write_text("fake cnv")
    (ladcp_mount / "003DL000.000").write_text("")
    (ladcp_mount / "003UL000.000").write_text("")
    monkeypatch.setitem(config.MOUNTS, "data", data_mount)
    monkeypatch.setitem(config.MOUNTS, "ctd", ctd_mount)
    monkeypatch.setitem(config.MOUNTS, "ladcp", ladcp_mount)

    session = CruiseSession(casts=[_valid_cast(
        ctd="quick_convert/cast.UNVALIDATED_QUICKCONVERT.cnv",
    )])

    result = validation.validate_session(session)

    assert result.warnings == {}
