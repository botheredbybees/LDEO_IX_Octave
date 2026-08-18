from webapp import delimited_parser


def test_sniffs_zero_header_lines_and_field_count(tmp_path):
    f = tmp_path / "003.2Hz"
    f.write_text(
        "1523980583.0 5.234 12.10 34.90 0 0 0 0 0 -15.498335 -150.196990\n"
        "1523980584.0 5.240 12.11 34.91 0 0 0 0 0 -15.498336 -150.196991\n"
    )

    preview = delimited_parser.sniff_and_preview(f)

    assert preview.header_lines == 0
    assert preview.fields_per_line == 11
    assert preview.preview_rows[0][0] == "1523980583.0"
    assert len(preview.preview_rows) == 2


def test_sniffs_header_lines_before_numeric_data(tmp_path):
    f = tmp_path / "with_header.txt"
    f.write_text(
        "% CTD decimated series\n"
        "% generated 2015-04-11\n"
        "1.0 2.0 3.0\n"
        "4.0 5.0 6.0\n"
    )

    preview = delimited_parser.sniff_and_preview(f)

    assert preview.header_lines == 2
    assert preview.fields_per_line == 3


def test_limits_preview_rows_to_max_rows(tmp_path):
    f = tmp_path / "long.txt"
    f.write_text("\n".join(f"{i}.0 {i}.1" for i in range(20)) + "\n")

    preview = delimited_parser.sniff_and_preview(f, max_rows=5)

    assert len(preview.preview_rows) == 5


def test_empty_file_returns_zero_fields(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("")

    preview = delimited_parser.sniff_and_preview(f)

    assert preview.fields_per_line == 0
    assert preview.preview_rows == []


def test_extracts_column_names_from_last_matching_length_header_line(tmp_path):
    f = tmp_path / "cast.all"
    f.write_text(
        " START POSITION   : 67 00.08 S 039 59.81 E\n"
        "CTDPRS     CTDTMP    CTDCOND     CTDSAL    CTDOXY     FLUORO        PAR      TRANS   NPTS\n"
        "   DBAR     ITS-90      mS/cm     PSS-78    umol/l\n"
        "    2.0    -9.0000  -9.000000    -9.0000     -9.00     -9.000     -9.000     -9.000      0\n"
        "    4.0     0.1258  27.718977    33.1138    355.47      1.382      0.002     -0.001     22\n"
    )

    preview = delimited_parser.sniff_and_preview(f)

    assert preview.column_names == [
        "CTDPRS", "CTDTMP", "CTDCOND", "CTDSAL", "CTDOXY",
        "FLUORO", "PAR", "TRANS", "NPTS",
    ]


def test_ignores_comment_marked_header_lines_for_column_names(tmp_path):
    f = tmp_path / "with_header.txt"
    f.write_text(
        "% CTD decimated series\n"
        "% generated 2015-04-11\n"
        "1.0 2.0 3.0\n"
        "4.0 5.0 6.0\n"
    )

    preview = delimited_parser.sniff_and_preview(f)

    assert preview.column_names is None
    # existing behavior must be unaffected
    assert preview.header_lines == 2
    assert preview.fields_per_line == 3


def test_column_names_is_none_for_headerless_files(tmp_path):
    f = tmp_path / "003.2Hz"
    f.write_text(
        "1523980583.0 5.234 12.10 34.90 0 0 0 0 0 -15.498335 -150.196990\n"
        "1523980584.0 5.240 12.11 34.91 0 0 0 0 0 -15.498336 -150.196991\n"
    )

    preview = delimited_parser.sniff_and_preview(f)

    assert preview.column_names is None
