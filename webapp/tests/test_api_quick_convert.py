from fastapi.testclient import TestClient

from webapp import config, main, quick_convert


def test_quick_convert_ctd_success(tmp_path, monkeypatch):
    ctd_mount = tmp_path / "ctd"
    data_mount = tmp_path / "data"
    ctd_mount.mkdir()
    data_mount.mkdir()
    (ctd_mount / "cast.hex").write_text("fake hex")
    (ctd_mount / "cast.XMLCON").write_text("fake xmlcon")
    monkeypatch.setitem(config.MOUNTS, "ctd", ctd_mount)
    monkeypatch.setitem(config.MOUNTS, "data", data_mount)

    def _fake_convert(hex_path, xmlcon_path, data_mount_root):
        assert hex_path == ctd_mount / "cast.hex"
        assert xmlcon_path == ctd_mount / "cast.XMLCON"
        assert data_mount_root == data_mount
        return "quick_convert/cast.UNVALIDATED_QUICKCONVERT.cnv"

    monkeypatch.setattr(quick_convert, "convert", _fake_convert)

    client = TestClient(main.app)
    response = client.post(
        "/api/quick-convert/ctd",
        json={"hex_path": "cast.hex", "xmlcon_path": "cast.XMLCON"},
    )

    assert response.status_code == 200
    assert response.json() == {"ctd_path": "quick_convert/cast.UNVALIDATED_QUICKCONVERT.cnv"}


def test_quick_convert_ctd_rejects_path_traversal(tmp_path, monkeypatch):
    ctd_mount = tmp_path / "ctd"
    data_mount = tmp_path / "data"
    ctd_mount.mkdir()
    data_mount.mkdir()
    monkeypatch.setitem(config.MOUNTS, "ctd", ctd_mount)
    monkeypatch.setitem(config.MOUNTS, "data", data_mount)

    client = TestClient(main.app)
    response = client.post(
        "/api/quick-convert/ctd",
        json={"hex_path": "../../etc/passwd", "xmlcon_path": "cast.XMLCON"},
    )

    assert response.status_code == 400


def test_quick_convert_ctd_surfaces_conversion_error(tmp_path, monkeypatch):
    ctd_mount = tmp_path / "ctd"
    data_mount = tmp_path / "data"
    ctd_mount.mkdir()
    data_mount.mkdir()
    (ctd_mount / "cast.hex").write_text("fake hex")
    (ctd_mount / "cast.XMLCON").write_text("fake xmlcon")
    monkeypatch.setitem(config.MOUNTS, "ctd", ctd_mount)
    monkeypatch.setitem(config.MOUNTS, "data", data_mount)

    def _fake_convert(hex_path, xmlcon_path, data_mount_root):
        raise quick_convert.QuickConvertError("could not convert cast.hex: bad checksum")

    monkeypatch.setattr(quick_convert, "convert", _fake_convert)

    client = TestClient(main.app)
    response = client.post(
        "/api/quick-convert/ctd",
        json={"hex_path": "cast.hex", "xmlcon_path": "cast.XMLCON"},
    )

    assert response.status_code == 400
    assert "bad checksum" in response.json()["detail"]
