from webapp import ladcp_scan


def test_pairs_down_and_up_files_by_station(tmp_path):
    (tmp_path / "003DL000.000").write_text("")
    (tmp_path / "003UL000.000").write_text("")
    (tmp_path / "004DL000.000").write_text("")

    results = ladcp_scan.scan_ladcp_directory(tmp_path)

    by_station = {r.station: r for r in results}
    assert by_station["003"].down == "003DL000.000"
    assert by_station["003"].up == "003UL000.000"
    assert by_station["004"].down == "004DL000.000"
    assert by_station["004"].up is None


def test_ignores_files_that_dont_match_the_convention(tmp_path):
    (tmp_path / "readme.txt").write_text("")
    (tmp_path / "003DL000.000").write_text("")

    results = ladcp_scan.scan_ladcp_directory(tmp_path)

    assert len(results) == 1
    assert results[0].station == "003"


def test_results_sorted_by_station(tmp_path):
    (tmp_path / "010DL000.000").write_text("")
    (tmp_path / "002DL000.000").write_text("")

    results = ladcp_scan.scan_ladcp_directory(tmp_path)

    assert [r.station for r in results] == ["002", "010"]
