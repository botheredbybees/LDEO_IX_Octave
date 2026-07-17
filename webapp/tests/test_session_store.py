from webapp import config, session_store
from webapp.models import CastEntry, CruiseSession


def test_load_session_returns_empty_session_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)

    session = session_store.load_session()

    assert session.cruise_id == ""
    assert session.casts == []


def test_save_then_load_round_trips_cast_data(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)

    session = CruiseSession(cruise_id="P16N", casts=[
        CastEntry(cast_name="003", lat=-15.498335, lon=-150.19699)
    ])
    session_store.save_session(session)

    loaded = session_store.load_session()

    assert loaded.cruise_id == "P16N"
    assert len(loaded.casts) == 1
    assert loaded.casts[0].cast_name == "003"
    assert loaded.casts[0].lat == -15.498335


def test_session_file_written_at_expected_path(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)

    session_store.save_session(CruiseSession())

    assert session_store.session_path() == tmp_path / ".cruise_intake_session.json"
    assert session_store.session_path().is_file()
