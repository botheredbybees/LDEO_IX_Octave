from pathlib import Path

import pytest

from webapp import quick_convert

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "test_data" / "202324050_nuyina" / "ctd" / "seasave_raw"
FIXTURE_HEX = FIXTURE_DIR / "202324050_002.hex"
FIXTURE_XMLCON = FIXTURE_DIR / "202324050_002.XMLCON"


def test_convert_writes_cnv_under_quick_convert_dir(tmp_path):
    if not FIXTURE_HEX.is_file():
        pytest.skip("test_data/ fixture not present in this checkout")

    result = quick_convert.convert(FIXTURE_HEX, FIXTURE_XMLCON, tmp_path)

    assert result == "quick_convert/202324050_002.UNVALIDATED_QUICKCONVERT.cnv"
    written = tmp_path / "quick_convert" / "202324050_002.UNVALIDATED_QUICKCONVERT.cnv"
    assert written.is_file()
    assert written.stat().st_size > 0


def test_convert_output_is_previewable(tmp_path):
    if not FIXTURE_HEX.is_file():
        pytest.skip("test_data/ fixture not present in this checkout")

    from webapp import delimited_parser

    result = quick_convert.convert(FIXTURE_HEX, FIXTURE_XMLCON, tmp_path)
    written = tmp_path / result

    preview = delimited_parser.sniff_and_preview(written)

    assert preview.fields_per_line > 0
    assert len(preview.preview_rows) > 0


def test_convert_raises_quick_convert_error_for_missing_hex(tmp_path):
    with pytest.raises(quick_convert.QuickConvertError):
        quick_convert.convert(tmp_path / "does_not_exist.hex", tmp_path / "does_not_exist.XMLCON", tmp_path)
