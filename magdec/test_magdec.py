import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from magdec import compute, main

SCRIPT = Path(__file__).resolve().parent / "magdec.py"

# Real position/date from voyage 202324050 cast 005, processed for real
# this session. The already-known-good magdev.m (year-2000 IGRF00)
# fallback declination for this exact position was 15.057159 degrees,
# independently confirmed multiple times this session. A correct,
# modern (IGRF-14, 2024) computation for the same real position lands
# in the same ballpark (same sign, small delta -- secular variation
# over ~25 years is real but bounded), not a sign flip or wild
# divergence -- confirmed directly this session: 15.883 degrees.
CAST_005_LON = 148.490637
CAST_005_LAT = -42.559128


def test_compute_matches_known_sign_and_magnitude_for_real_cast_005_position():
    declination, inclination, horizontal, total = compute(
        CAST_005_LON, CAST_005_LAT, 2024, 6, 17
    )

    assert 10.0 < declination < 20.0
    assert -90.0 <= inclination <= 90.0
    assert 1000.0 < horizontal < 100000.0
    assert 1000.0 < total < 100000.0


def test_main_with_no_args_exits_1_with_usage_on_stderr(capsys):
    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "usage" in captured.err.lower()


def test_main_with_wrong_arg_count_exits_1():
    exit_code = main(["148.49", "-42.56", "2024"])

    assert exit_code == 1


def test_main_with_five_args_exits_0_and_prints_four_numbers(capsys):
    exit_code = main(["148.490637", "-42.559128", "2024", "6", "17"])

    captured = capsys.readouterr()
    assert exit_code == 0
    values = [float(x) for x in captured.out.split()]
    assert len(values) == 4


def test_cli_no_args_real_subprocess_exits_1():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True
    )

    assert result.returncode == 1
    assert "usage" in result.stderr.lower()


def test_cli_five_args_real_subprocess_exits_0():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "148.490637", "-42.559128", "2024", "6", "17"],
        capture_output=True, text=True,
    )

    assert result.returncode == 0
    values = [float(x) for x in result.stdout.split()]
    assert len(values) == 4
    assert 10.0 < values[0] < 20.0
