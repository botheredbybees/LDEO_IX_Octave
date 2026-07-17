from pathlib import Path

import pytest

from webapp import paths


def test_resolves_simple_relative_path(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "file.txt").write_text("hi")

    result = paths.resolve_within(tmp_path, "sub/file.txt")

    assert result == (tmp_path / "sub" / "file.txt").resolve()


def test_empty_relative_path_resolves_to_root(tmp_path):
    result = paths.resolve_within(tmp_path, "")
    assert result == tmp_path.resolve()


def test_rejects_dotdot_traversal(tmp_path):
    with pytest.raises(paths.PathOutsideMountError):
        paths.resolve_within(tmp_path, "../outside.txt")


def test_rejects_dotdot_in_middle_of_path(tmp_path):
    with pytest.raises(paths.PathOutsideMountError):
        paths.resolve_within(tmp_path, "sub/../../outside.txt")


def test_rejects_absolute_path(tmp_path):
    with pytest.raises(paths.PathOutsideMountError):
        paths.resolve_within(tmp_path, "/etc/passwd")
