from fastapi.testclient import TestClient
from scipy.io import netcdf_file

from webapp import config, main


def test_get_session_starts_empty(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)

    client = TestClient(main.app)
    response = client.get("/api/session")

    assert response.status_code == 200
    assert response.json()["casts"] == []


def test_create_cast_persists_to_session(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)
    client = TestClient(main.app)

    response = client.post("/api/session/casts", json={"cast_name": "003", "ladcp_station": 3})

    assert response.status_code == 201
    body = response.json()
    assert body["cast_name"] == "003"
    assert body["checkpoints_file"] == "checkpoints/003"
    assert body["res_file"] == "V7/003"

    session = client.get("/api/session").json()
    assert len(session["casts"]) == 1


def test_update_cast_changes_fields(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)
    client = TestClient(main.app)
    created = client.post("/api/session/casts", json={"cast_name": "003"}).json()

    response = client.put(f"/api/session/casts/{created['id']}", json={"lat": -15.5})

    assert response.status_code == 200
    assert response.json()["lat"] == -15.5


def test_delete_cast_removes_it(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)
    client = TestClient(main.app)
    created = client.post("/api/session/casts", json={"cast_name": "003"}).json()

    response = client.delete(f"/api/session/casts/{created['id']}")

    assert response.status_code == 204
    assert client.get("/api/session").json()["casts"] == []


def test_clone_cast_creates_copy_with_new_id(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)
    client = TestClient(main.app)
    created = client.post("/api/session/casts", json={"cast_name": "003", "lat": -15.5}).json()

    response = client.post(f"/api/session/casts/{created['id']}/clone")

    assert response.status_code == 201
    clone = response.json()
    assert clone["id"] != created["id"]
    assert clone["lat"] == -15.5


def test_clone_from_netcdf_prefills_known_fields(tmp_path, monkeypatch):
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)
    nc_path = tmp_path / "003.nc"
    nc = netcdf_file(str(nc_path), "w")
    nc.createDimension("one", 1)
    var = nc.createVariable("placeholder", "f8", ("one",))
    var[:] = 0.0
    nc.lat = -15.498335
    nc.lon = -150.19699
    nc.close()
    monkeypatch.setitem(config.MOUNTS, "data", tmp_path)

    client = TestClient(main.app)
    response = client.post("/api/session/casts/from-netcdf", params={"path": "003.nc"})

    assert response.status_code == 201
    body = response.json()
    assert body["lat"] == -15.498335
    assert body["lon"] == -150.19699
