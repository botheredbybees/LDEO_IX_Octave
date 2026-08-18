from pathlib import Path

QUICKCONVERT_SUFFIX = ".UNVALIDATED_QUICKCONVERT.cnv"


class QuickConvertError(Exception):
    pass


def convert(hex_path: Path, xmlcon_path: Path, data_mount_root: Path) -> str:
    if not hex_path.is_file():
        raise QuickConvertError(f"{hex_path} not found")
    if not xmlcon_path.is_file():
        raise QuickConvertError(f"{xmlcon_path} not found")

    output_dir = data_mount_root / "quick_convert"
    output_name = f"{hex_path.stem}{QUICKCONVERT_SUFFIX}"
    output_path = output_dir / output_name

    try:
        from ctdam.conv import decode_hex

        output_dir.mkdir(parents=True, exist_ok=True)
        ctd_data = decode_hex(hex_path, xmlcon_path)
        ctd_data.to_cnv(str(output_path))
    except Exception as exc:
        raise QuickConvertError(f"could not convert {hex_path.name}: {exc}") from exc

    return f"quick_convert/{output_name}"
