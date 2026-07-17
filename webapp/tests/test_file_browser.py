from webapp import file_browser


def test_lists_files_and_dirs_sorted_dirs_first(tmp_path):
    (tmp_path / "zeta.txt").write_text("a")
    (tmp_path / "alpha_dir").mkdir()
    (tmp_path / "beta.txt").write_text("b")

    entries = file_browser.list_directory(tmp_path)

    names = [e.name for e in entries]
    assert names == ["alpha_dir", "beta.txt", "zeta.txt"]
    assert entries[0].is_dir is True
    assert entries[1].is_dir is False


def test_relative_path_is_reported_for_nested_entries(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "file.txt").write_text("a")

    entries = file_browser.list_directory(tmp_path, "sub")

    assert entries[0].relative_path == "sub/file.txt"


def test_raises_for_traversal_attempt(tmp_path):
    from webapp import paths

    try:
        file_browser.list_directory(tmp_path, "../")
        assert False, "expected PathOutsideMountError"
    except paths.PathOutsideMountError:
        pass
