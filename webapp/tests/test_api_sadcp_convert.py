from fastapi.testclient import TestClient

from webapp import config, main, sadcp_convert


def test_sadcp_convert_success(tmp_path, monkeypatch):
    codas_mount = tmp_path / "codas"
    data_mount = tmp_path / "data"
    contour_dir = codas_mount / "os150nb" / "contour"
    contour_dir.mkdir(parents=True)
    data_mount.mkdir()
    monkeypatch.setitem(config.MOUNTS, "codas", codas_mount)
    monkeypatch.setitem(config.MOUNTS, "data", data_mount)

    def _fake_convert(contour_dir_arg, data_mount_root):
        assert contour_dir_arg == contour_dir
        assert data_mount_root == data_mount
        return "sadcp_convert/os150nb.SADCP.mat"

    monkeypatch.setattr(sadcp_convert, "convert", _fake_convert)

    client = TestClient(main.app)
    response = client.post("/api/sadcp/convert", json={"contour_dir": "os150nb/contour"})

    assert response.status_code == 200
    assert response.json() == {"sadcp_path": "sadcp_convert/os150nb.SADCP.mat"}


def test_sadcp_convert_rejects_path_traversal(tmp_path, monkeypatch):
    codas_mount = tmp_path / "codas"
    data_mount = tmp_path / "data"
    codas_mount.mkdir()
    data_mount.mkdir()
    monkeypatch.setitem(config.MOUNTS, "codas", codas_mount)
    monkeypatch.setitem(config.MOUNTS, "data", data_mount)

    client = TestClient(main.app)
    response = client.post("/api/sadcp/convert", json={"contour_dir": "../../etc"})

    assert response.status_code == 400


def test_sadcp_convert_surfaces_conversion_error(tmp_path, monkeypatch):
    codas_mount = tmp_path / "codas"
    data_mount = tmp_path / "data"
    codas_mount.mkdir()
    data_mount.mkdir()
    monkeypatch.setitem(config.MOUNTS, "codas", codas_mount)
    monkeypatch.setitem(config.MOUNTS, "data", data_mount)

    def _fake_convert(contour_dir_arg, data_mount_root):
        raise sadcp_convert.SadcpConvertError("contour_xy.mat not found")

    monkeypatch.setattr(sadcp_convert, "convert", _fake_convert)

    client = TestClient(main.app)
    response = client.post("/api/sadcp/convert", json={"contour_dir": "os150nb/contour"})

    assert response.status_code == 400
    assert "contour_xy.mat not found" in response.json()["detail"]


def test_sadcp_convert_rejects_missing_codas_mount(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "codas", tmp_path / "does-not-exist")

    client = TestClient(main.app)
    response = client.post("/api/sadcp/convert", json={"contour_dir": "os150nb/contour"})

    assert response.status_code == 404


def test_mounts_endpoint_includes_codas_when_configured(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "codas", tmp_path)

    client = TestClient(main.app)
    response = client.get("/api/mounts")

    assert "codas" in response.json()["mounts"]
