from fastapi.testclient import TestClient

from webapp import config, main


def test_mounts_endpoint_lists_only_existing_dirs(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "ctd", tmp_path)
    monkeypatch.setitem(config.MOUNTS, "sadcp", tmp_path / "does-not-exist")

    client = TestClient(main.app)
    response = client.get("/api/mounts")

    assert response.status_code == 200
    assert "ctd" in response.json()["mounts"]
    assert "sadcp" not in response.json()["mounts"]


def test_browse_endpoint_lists_directory_contents(tmp_path, monkeypatch):
    (tmp_path / "cast1.cnv").write_text("data")
    monkeypatch.setitem(config.MOUNTS, "ctd", tmp_path)

    client = TestClient(main.app)
    response = client.get("/api/browse/ctd")

    assert response.status_code == 200
    names = [e["name"] for e in response.json()["entries"]]
    assert names == ["cast1.cnv"]


def test_browse_endpoint_rejects_unknown_mount():
    client = TestClient(main.app)
    response = client.get("/api/browse/nope")
    assert response.status_code == 404


def test_browse_endpoint_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "ctd", tmp_path)

    client = TestClient(main.app)
    response = client.get("/api/browse/ctd", params={"path": "../../etc"})

    assert response.status_code == 400


def test_preview_endpoint_returns_sniffed_structure(tmp_path, monkeypatch):
    (tmp_path / "cast1.cnv").write_text("1.0 2.0 3.0\n4.0 5.0 6.0\n")
    monkeypatch.setitem(config.MOUNTS, "ctd", tmp_path)

    client = TestClient(main.app)
    response = client.get("/api/preview/ctd", params={"path": "cast1.cnv"})

    assert response.status_code == 200
    body = response.json()
    assert body["header_lines"] == 0
    assert body["fields_per_line"] == 3


def test_preview_endpoint_returns_column_names_and_suggested_roles(tmp_path, monkeypatch):
    (tmp_path / "cast1.all").write_text(
        "CTDPRS     CTDTMP    CTDSAL\n"
        "    2.0    -9.0000    -9.0000\n"
        "    4.0     0.1258    33.1138\n"
    )
    monkeypatch.setitem(config.MOUNTS, "ctd", tmp_path)

    client = TestClient(main.app)
    response = client.get("/api/preview/ctd", params={"path": "cast1.all"})

    assert response.status_code == 200
    body = response.json()
    assert body["column_names"] == ["CTDPRS", "CTDTMP", "CTDSAL"]
    assert body["suggested_roles"] == {"pressure": 1, "temperature": 2, "salinity": 3}


def test_preview_endpoint_returns_null_column_names_for_headerless_file(tmp_path, monkeypatch):
    (tmp_path / "cast1.cnv").write_text("1.0 2.0 3.0\n4.0 5.0 6.0\n")
    monkeypatch.setitem(config.MOUNTS, "ctd", tmp_path)

    client = TestClient(main.app)
    response = client.get("/api/preview/ctd", params={"path": "cast1.cnv"})

    assert response.status_code == 200
    body = response.json()
    assert body["column_names"] is None
    assert body["suggested_roles"] == {}


def test_ladcp_scan_endpoint(tmp_path, monkeypatch):
    (tmp_path / "003DL000.000").write_text("")
    (tmp_path / "003UL000.000").write_text("")
    monkeypatch.setitem(config.MOUNTS, "ladcp", tmp_path)

    client = TestClient(main.app)
    response = client.get("/api/ladcp/scan")

    assert response.status_code == 200
    casts = response.json()["casts"]
    assert casts == [{"station": "003", "down": "003DL000.000", "up": "003UL000.000"}]
