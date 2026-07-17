from scipy.io import netcdf_file

from webapp import netcdf_reader


def _write_fixture_nc(path):
    nc = netcdf_file(path, "w")
    nc.createDimension("one", 1)
    var = nc.createVariable("placeholder", "f8", ("one",))
    var[:] = 0.0
    nc.lat = -15.498335
    nc.lon = -150.19699
    nc.drot = 12.318441
    nc.name = "003"
    nc.close()


def test_reads_global_attributes_written_by_scipy(tmp_path):
    nc_path = tmp_path / "003.nc"
    _write_fixture_nc(nc_path)

    attrs = netcdf_reader.read_global_attributes(nc_path)

    assert attrs["lat"] == -15.498335
    assert attrs["lon"] == -150.19699
    assert attrs["drot"] == 12.318441
    assert attrs["name"] == "003"


def test_missing_file_raises_file_not_found_error(tmp_path):
    import pytest

    with pytest.raises(FileNotFoundError):
        netcdf_reader.read_global_attributes(tmp_path / "missing.nc")
