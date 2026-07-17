from datetime import datetime

from fastapi.testclient import TestClient

from webapp import config, main


def _valid_cast_payload(**overrides):
    payload = dict(
        cast_name="003",
        ladcpdo="003DL000.000",
        ladcpup="003UL000.000",
        ladcp_station=3,
        ladcp_cast=1,
        lat=-15.5,
        lon=-150.2,
        time_start=[2015, 4, 11, 17, 36, 23.0],
        time_end=[2015, 4, 11, 21, 9, 42.0],
    )
    payload.update(overrides)
    return payload


def test_generate_blocked_when_required_fields_missing(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)
    client = TestClient(main.app)
    client.post("/api/session/casts", json={"cast_name": "003"})

    response = client.post("/api/generate")

    assert response.status_code == 400
    assert "errors" in response.json()
    assert not (tmp_path / "set_cast_params.m").exists()


def test_generate_writes_file_when_valid(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)
    client = TestClient(main.app)
    client.post("/api/session/casts", json=_valid_cast_payload())

    response = client.post("/api/generate")

    assert response.status_code == 200
    written = tmp_path / "set_cast_params.m"
    assert written.is_file()
    assert "case 3" in written.read_text()


def test_generate_backs_up_existing_file(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)
    existing = tmp_path / "set_cast_params.m"
    existing.write_text("% hand-written\n")
    client = TestClient(main.app)
    client.post("/api/session/casts", json=_valid_cast_payload())

    client.post("/api/generate")

    backups = list(tmp_path.glob("set_cast_params.m.bak.*"))
    assert len(backups) == 1
    assert backups[0].read_text() == "% hand-written\n"
