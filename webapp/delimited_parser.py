from dataclasses import dataclass
from pathlib import Path


@dataclass
class DelimitedPreview:
    header_lines: int
    fields_per_line: int
    preview_rows: list


def sniff_and_preview(file_path: Path, max_rows: int = 10) -> DelimitedPreview:
    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
        lines = [line.rstrip("\n") for line in fh if line.strip() != ""]

    header_lines = 0
    for line in lines:
        tokens = line.strip().split()
        if tokens and all(_is_number(tok) for tok in tokens):
            break
        header_lines += 1

    data_lines = lines[header_lines:]
    fields_per_line = len(data_lines[0].split()) if data_lines else 0
    preview_rows = [line.split() for line in data_lines[:max_rows]]

    return DelimitedPreview(
        header_lines=header_lines,
        fields_per_line=fields_per_line,
        preview_rows=preview_rows,
    )


def _is_number(token: str) -> bool:
    try:
        float(token)
        return True
    except ValueError:
        return False
