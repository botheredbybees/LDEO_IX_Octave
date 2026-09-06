import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gngga_to_navtable import convert, nmea_to_decimal, _parse_cast_start

FIXTURE_CSV = """datetime,msg_id,gps_time_dgps_gga,latitude_dgps_gga,n_or_s_dgps_gga,longitude_dgps_gga,e_or_w_dgps_gga,fix_quality_dgps_gga,number_of_satellites_dgps_gga,horizontal_dilution_of_precision_dgps_gga,antenna_height_dgps_gga,geoid_height_above_reference_ellipsoid_dgps_gga,last_dgps_update_dgps_gga,differential_reference_station_id_dgps_gga
2024-06-17T00:44:58.000000Z,$GNGGA,004458.00,4233.6601,S,14829.5473,E,1,14,0.7,35.3,M,-4.7,M,,
2024-06-17T00:45:08.000000Z,$GNGGA,004508.00,4233.6620,S,14829.5480,E,1,14,0.7,35.3,M,-4.7,M,,
"""


def test_nmea_to_decimal_south_and_east_are_negative_and_positive():
    assert nmea_to_decimal("4233.6601", "S") == -(42 + 33.6601 / 60)
    assert nmea_to_decimal("14829.5473", "E") == 148 + 29.5473 / 60


def test_nmea_to_decimal_north_and_west():
    assert nmea_to_decimal("4233.6601", "N") == 42 + 33.6601 / 60
    assert nmea_to_decimal("14829.5473", "W") == -(148 + 29.5473 / 60)


def test_parse_cast_start_accepts_z_suffix():
    parsed = _parse_cast_start("2024-06-17T00:44:58Z")
    assert parsed == datetime(2024, 6, 17, 0, 44, 58, tzinfo=timezone.utc)


def test_convert_computes_elapsed_seconds_relative_to_cast_start(tmp_path):
    csv_path = tmp_path / "GNGGA_2024-06-17.csv"
    csv_path.write_text(FIXTURE_CSV)
    out_path = tmp_path / "out.navtable"
    cast_start = datetime(2024, 6, 17, 0, 44, 58, tzinfo=timezone.utc)

    rows_written = convert(str(csv_path), str(out_path), cast_start)

    assert rows_written == 2
    lines = out_path.read_text().splitlines()
    first_elapsed, first_lat, first_lon = (float(x) for x in lines[0].split())
    second_elapsed, _, _ = (float(x) for x in lines[1].split())
    assert first_elapsed == 0.0
    assert second_elapsed == 10.0
    assert round(first_lat, 6) == round(-(42 + 33.6601 / 60), 6)
    assert round(first_lon, 6) == round(148 + 29.5473 / 60, 6)


def test_convert_produces_different_elapsed_times_for_different_cast_starts(tmp_path):
    csv_path = tmp_path / "GNGGA_2024-06-17.csv"
    csv_path.write_text(FIXTURE_CSV)
    out_a = tmp_path / "a.navtable"
    out_b = tmp_path / "b.navtable"

    convert(str(csv_path), str(out_a), datetime(2024, 6, 17, 0, 44, 58, tzinfo=timezone.utc))
    convert(str(csv_path), str(out_b), datetime(2024, 6, 17, 3, 43, 15, tzinfo=timezone.utc))

    first_elapsed_a = float(out_a.read_text().splitlines()[0].split()[0])
    first_elapsed_b = float(out_b.read_text().splitlines()[0].split()[0])
    assert first_elapsed_a != first_elapsed_b


def test_cli_requires_cast_start_flag(tmp_path):
    csv_path = tmp_path / "GNGGA_2024-06-17.csv"
    csv_path.write_text(FIXTURE_CSV)
    out_path = tmp_path / "out.navtable"

    script = Path(__file__).resolve().parent / "gngga_to_navtable.py"
    result = subprocess.run(
        [sys.executable, str(script), str(csv_path), str(out_path)],
        capture_output=True, text=True,
    )

    assert result.returncode != 0
    assert "--cast-start" in result.stderr


def test_cli_writes_navtable_when_cast_start_given(tmp_path):
    csv_path = tmp_path / "GNGGA_2024-06-17.csv"
    csv_path.write_text(FIXTURE_CSV)
    out_path = tmp_path / "out.navtable"

    script = Path(__file__).resolve().parent / "gngga_to_navtable.py"
    result = subprocess.run(
        [sys.executable, str(script), str(csv_path), str(out_path),
         "--cast-start", "2024-06-17T00:44:58Z"],
        capture_output=True, text=True,
    )

    assert result.returncode == 0
    assert out_path.is_file()
    assert "wrote 2 rows" in result.stdout
