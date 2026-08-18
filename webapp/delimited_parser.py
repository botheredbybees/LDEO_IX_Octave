from dataclasses import dataclass
from pathlib import Path


@dataclass
class DelimitedPreview:
    header_lines: int
    fields_per_line: int
    preview_rows: list
    column_names: list | None = None


def sniff_and_preview(file_path: Path, max_rows: int = 10) -> DelimitedPreview:
    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
        lines = [line.rstrip("\n") for line in fh if line.strip() != ""]

    header_lines = 0
    header_line_texts = []
    for line in lines:
        tokens = line.strip().split()
        if tokens and all(_is_number(tok) for tok in tokens):
            break
        header_lines += 1
        header_line_texts.append(line)

    data_lines = lines[header_lines:]
    fields_per_line = len(data_lines[0].split()) if data_lines else 0
    preview_rows = [line.split() for line in data_lines[:max_rows]]

    # The real column-name row, when one exists, is the header line whose
    # token count matches the data row width -- skipping comment-marked
    # lines (`%`/`#`), which can coincidentally match by token count (see
    # test_ignores_comment_marked_header_lines_for_column_names). Real
    # files can have an earlier metadata line that also coincidentally
    # matches (e.g. a lat/lon line with as many tokens as the data), so
    # this takes the LAST match, not the first -- confirmed against a
    # real BROKE-West .all file where an earlier "START POSITION" line
    # has the same token count as the true CTDPRS/CTDTMP/... header.
    column_names = None
    if fields_per_line:
        for header_line in header_line_texts:
            stripped = header_line.strip()
            if stripped.startswith("%") or stripped.startswith("#"):
                continue
            tokens = stripped.split()
            if len(tokens) == fields_per_line:
                column_names = tokens

    return DelimitedPreview(
        header_lines=header_lines,
        fields_per_line=fields_per_line,
        preview_rows=preview_rows,
        column_names=column_names,
    )


def _is_number(token: str) -> bool:
    try:
        float(token)
        return True
    except ValueError:
        return False
